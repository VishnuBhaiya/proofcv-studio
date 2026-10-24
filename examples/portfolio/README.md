# Shared fictional portfolio demonstration

`avery-demo.json` contains only the labelled fictional Avery story, source IDs,
role views and appearance settings. The four-project profile is defined in
`server/seed_labelled_sample.py`. Neither file contains a private workspace DB.

`solarvision-demo.mp4` is the user-supplied SolarVision application walkthrough,
bundled for the group demonstration. Its opening contains solar-energy context
footage; application controls and inspection dashboards appear later. Including
the recording in this fictional CV does not claim that Avery authored SolarVision
or establish deployment, accuracy or workplace outcomes.

Use `python -m server.prepare_team_demo --apply` after project setup. The helper
verifies the video checksum and exact confirmed demo profile, then prepares only
a new portfolio draft. It never overwrites an existing custom portfolio and never
creates an approved snapshot. Review the draft in Portfolio Studio before export.
