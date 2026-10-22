import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from server.gemini import GeminiDecisionModel, GeminiError, GeminiFallbackModel, GeminiSettings


class GeminiAdapterTests(unittest.TestCase):
    def model(self):
        return GeminiDecisionModel(GeminiSettings("test-secret", "gemini-test"))

    def response(self, text='{"type":"final_answer","answer":"Hello"}', finish="STOP"):
        return io.BytesIO(json.dumps({"candidates": [{"finishReason": finish,
            "content": {"parts": [{"text": text}]}}]}).encode())

    def test_missing_configuration_never_calls_network(self):
        with patch("urllib.request.urlopen") as call:
            with self.assertRaises(GeminiError):
                GeminiDecisionModel(GeminiSettings()).decide([], {})
            call.assert_not_called()

    def test_key_excluded_from_repr_and_status(self):
        settings = self.model().settings
        self.assertNotIn("test-secret", repr(settings))
        self.assertNotIn("test-secret", json.dumps(settings.public_status()))
        self.assertFalse(settings.public_status()["connection_verified"])

    def test_runtime_status_reflects_verified_success_and_failure(self):
        model = GeminiFallbackModel(GeminiSettings("test-secret", "gemini-test", ("gemini-test",)))
        self.assertEqual(model.public_status()["availability"], "not_checked")
        with patch("urllib.request.urlopen", return_value=self.response()):
            model.decide([], {})
        self.assertTrue(model.public_status()["connection_verified"])
        self.assertEqual(model.public_status()["availability"], "available")
        self.assertEqual(model.public_status()["models_tried"], ["gemini-test"])
        failure = urllib.error.HTTPError("url", 403, "forbidden", {}, io.BytesIO(b""))
        with patch("urllib.request.urlopen", side_effect=failure):
            with self.assertRaises(GeminiError):
                model.decide([], {})
        self.assertFalse(model.public_status()["connection_verified"])
        self.assertEqual(model.public_status()["availability"], "unavailable")
        self.assertEqual(model.public_status()["models_tried"], ["gemini-test"])
        self.assertEqual(model.public_status()["failure_kind"], "configuration")

    def test_fallback_reports_every_retryable_model_attempt(self):
        models = ("gemini-first", "gemini-second", "gemini-third")
        model = GeminiFallbackModel(GeminiSettings("test-secret", models[0], models))
        failure = urllib.error.HTTPError("url", 503, "unavailable", {}, io.BytesIO(b""))
        with patch("urllib.request.urlopen", side_effect=failure) as call:
            with self.assertRaises(GeminiError) as caught:
                model.decide([], {})
        self.assertEqual(call.call_count, 3)
        self.assertEqual(model.public_status()["models_tried"], list(models))
        self.assertEqual(model.public_status()["failure_kind"], "temporary")
        self.assertEqual(caught.exception.quota_details["models_tried"], list(models))
        for configured_model in models:
            self.assertIn(configured_model, str(caught.exception))

    def test_fallback_stops_on_shared_non_retryable_configuration_error(self):
        models = ("gemini-first", "gemini-second", "gemini-third")
        model = GeminiFallbackModel(GeminiSettings("test-secret", models[0], models))
        failure = urllib.error.HTTPError("url", 403, "forbidden", {}, io.BytesIO(b""))
        with patch("urllib.request.urlopen", side_effect=failure) as call:
            with self.assertRaises(GeminiError):
                model.decide([], {})
        self.assertEqual(call.call_count, 1)
        self.assertEqual(model.public_status()["models_tried"], [models[0]])
        self.assertEqual(model.public_status()["failure_kind"], "configuration")

    def test_model_specific_404_tries_the_next_configured_model(self):
        models = ("gemini-retired", "gemini-working")
        model = GeminiFallbackModel(GeminiSettings("test-secret", models[0], models))
        missing = urllib.error.HTTPError("url", 404, "missing", {}, io.BytesIO(b""))
        with patch("urllib.request.urlopen", side_effect=[missing, self.response()]) as call:
            result = json.loads(model.decide([], {}))
        self.assertEqual(call.call_count, 2)
        self.assertEqual(result["answer"], "Hello")
        self.assertEqual(model.public_status()["models_tried"], list(models))
        self.assertEqual(model.public_status()["model"], models[1])
        self.assertEqual(model.public_status()["availability"], "available")

    def test_messages_and_observations_reach_gemini(self):
        with patch("urllib.request.urlopen", return_value=self.response()) as call:
            result = self.model().decide([
                {"role": "system", "content": "Tool policy"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": '{"type":"tool_call"}'},
                {"role": "user", "content": "Observation from Python"}], {"version": 2})
            request = call.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(json.loads(result)["answer"], "Hello")
            self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "Tool policy")
            self.assertIn('"version": 2', payload["contents"][-1]["parts"][-1]["text"])
            self.assertNotIn("test-secret", request.full_url)
            self.assertNotIn("test-secret", request.data.decode())

    def test_api_failure_sanitized_and_not_automatically_retried(self):
        for code in (400, 403, 404, 429, 503):
            with self.subTest(code=code):
                failure = urllib.error.HTTPError("url", code, "secret", {}, io.BytesIO(b"test-secret"))
                with patch("urllib.request.urlopen", side_effect=failure) as call:
                    with self.assertRaises(GeminiError) as caught:
                        self.model().decide([], {})
                    self.assertNotIn("test-secret", str(caught.exception))
                    self.assertEqual(caught.exception.retryable, code in (404, 429, 503))
                    self.assertEqual(call.call_count, 1)

    def test_incomplete_or_invalid_actions_rejected(self):
        for text, finish in [("[]", "STOP"), ("bad json", "STOP"), ('{}', "MAX_TOKENS")]:
            with self.subTest(text=text, finish=finish):
                with patch("urllib.request.urlopen", return_value=self.response(text, finish)):
                    with self.assertRaises(GeminiError):
                        self.model().decide([], {})

    def test_quota_details_exclude_free_text(self):
        body={'error':{'message':'test-secret', 'details':[
            {'@type':'type.googleapis.com/google.rpc.QuotaFailure','violations':[
                {'quotaId':'RequestsPerDay','quotaValue':'20','description':'test-secret'}]},
            {'@type':'type.googleapis.com/google.rpc.RetryInfo','retryDelay':'51s'}]}}
        failure=urllib.error.HTTPError('url',429,'test-secret',{},io.BytesIO(json.dumps(body).encode()))
        with patch('urllib.request.urlopen',side_effect=failure):
            with self.assertRaises(GeminiError) as caught:
                self.model().decide([], {})
        self.assertEqual(caught.exception.quota_details['retry_delay'],'51s')
        self.assertEqual(caught.exception.quota_details['violations'][0]['quotaId'],'RequestsPerDay')
        self.assertNotIn('test-secret',json.dumps(caught.exception.quota_details))

    def test_server_env_file_and_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("GEMINI_API_KEY='TEST_ONLY_PLACEHOLDER'\nGEMINI_MODEL=gemini-test\n", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(GeminiSettings.load(path).api_key, "TEST_ONLY_PLACEHOLDER")
            with patch.dict("os.environ", {"GEMINI_API_KEY": "env-secret"}, clear=True):
                self.assertEqual(GeminiSettings.load(path).api_key, "env-secret")


if __name__ == "__main__":
    unittest.main()
