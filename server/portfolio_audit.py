"""Read-only export/security audit; writes a generated result, never credentials."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from .service import ROOT
from .gemini import GeminiSettings


def main():
    result=sorted((ROOT/'runtime/evaluation').glob('showcase-live-*/result.json'))[-1]
    evidence=json.loads(result.read_text(encoding='utf-8'))
    raw=(result.parent/'approved-synthetic-portfolio.zip').read_bytes()
    checks={}
    settings=GeminiSettings.load()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        checks['all_manifest_hashes_match']=all(hashlib.sha256(archive.read(k)).hexdigest()==v for k,v in manifest['files'].items())
        checks['no_owner_or_private_files']=not any(x.startswith(('server/','src/','runtime/','.env')) or 'sqlite' in x for x in archive.namelist())
        blobs=[archive.read(name) for name in archive.namelist()]
        checks['no_api_key_in_export']=not settings.api_key or not any(settings.api_key.encode() in b for b in blobs)
        document=archive.read('index.html').decode()
        profile=evidence['portfolio']['profile']
        checks['contact_fields_hidden']=profile['email'] not in document and profile['phone'] not in document
        checks['portable_runtime_no_node_global']=b'process.env.NODE_ENV' not in archive.read('portfolio.js')
        checks['reviewed_image_video_and_narration_present']=all(any(x.endswith(ext) for x in archive.namelist()) for ext in ('.png','.mp4','.wav'))
        checks['general_and_two_role_views']=len(evidence['portfolio']['views'])==3
        view_orders={v['id']:v['project_ids'] for v in evidence['portfolio']['views']}
        checks['role_views_select_different_project_evidence']=view_orders['computer_vision_engineer']!=view_orders['graduate_ai_engineer']
        steps={s['name']:s for s in evidence['steps']}
        checks['recorded_reader_abstains_without_sources']=not steps['live_reader_abstention']['result']['sources'] and 'not stated' in steps['live_reader_abstention']['result']['answer']
        checks['recorded_reader_cites_public_project']=bool(steps['live_source_backed_reader']['result']['sources']) and steps['live_source_backed_reader']['result']['project_id'] in {p['id'] for p in evidence['portfolio']['projects']}
        checks['experience_retained']=profile['experience'] in json.loads(__import__('re').search(r'id="portfolio-data">(.*?)</script>',document,__import__('re').S).group(1))['person']['experience']
    # The key is compared in memory, never used as a shell argument or logged.
    source_files=[p for folder in ('src','server','dist','portfolio-runtime','docs') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    checks['no_api_key_in_shareable_sources']=not settings.api_key or not any(settings.api_key.encode() in p.read_bytes() for p in source_files)
    report=dict(input=str(result.relative_to(ROOT)),checks=checks,all_pass=all(checks.values()))
    output=ROOT/'runtime/evaluation/portfolio-export-audit.json'
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not report['all_pass']:raise SystemExit(1)


if __name__=='__main__':main()
