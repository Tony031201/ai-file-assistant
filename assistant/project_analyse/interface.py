from analyse.ingest import run_ingest
from summarize.summarize import run_summarize

def run_interface():
    run_ingest()
    run_summarize()

run_interface()