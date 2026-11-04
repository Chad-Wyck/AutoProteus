"""Authorization guard around the qualified frozen generation worker."""
from pathlib import Path
import sys
from neuron_focus_contract import require_execution

if __name__=='__main__':
    require_execution(Path(sys.argv[2]))
    from tensor_workspace_worker import main
    main(sys.argv[1:])
