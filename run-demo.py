"""Start the local IT-05 web experience from the repository root."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'projects/it-05-ticket-triage'))
from ticket_triage.web import main

if __name__ == '__main__':
    raise SystemExit(main())
