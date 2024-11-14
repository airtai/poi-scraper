from fastagency import FastAgency
from fastagency.ui.mesop import MesopUI

from ..workflow import wf

app = FastAgency(
    provider=wf,
    ui=MesopUI(),
    title="POI Scraper",
)

# start the fastagency app with the following command
# gunicorn poi_scraper.deployment.main:app
