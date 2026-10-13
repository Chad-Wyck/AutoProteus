"""Human-selected execution policy. Never read this choice from model settings."""
from dataclasses import dataclass
import sys

from .errors import IsolationError

NATIVE_WARNING = (
    'AutoProteus VM protection is disabled. Model-written code can access files, '
    'networks and credentials available to this account, including the controller. '
    'Use only a disposable machine or an environment you isolated yourself.'
)


@dataclass(frozen=True)
class ExecutionPolicy:
    mode: str = 'vm'
    acknowledge_host_access: bool = False

    def __post_init__(self):
        if self.mode not in ('vm', 'native'):
            raise ValueError('Execution mode must be vm or native')
        if self.mode == 'native':
            if self.acknowledge_host_access is not True:
                raise ValueError('Native execution requires --acknowledge-host-access. ' + NATIVE_WARNING)
            if sys.platform != 'linux':
                raise ValueError('Native execution currently supports Linux only')
        elif self.acknowledge_host_access:
            raise ValueError('--acknowledge-host-access requires --execution native')

    def public(self):
        return {'mode': self.mode, 'isolated': self.mode == 'vm',
                'label': 'Virtual machine' if self.mode == 'vm' else 'Without AutoProteus VM',
                'warning': NATIVE_WARNING if self.mode == 'native' else ''}


def add_execution_arguments(parser):
    parser.add_argument('--execution', choices=('vm', 'native'), default='vm',
                        help='VM isolation (default), or explicit Linux native execution.')
    parser.add_argument('--acknowledge-host-access', action='store_true',
                        help='Acknowledge that native code has this account\'s host access.')


def execution_from_args(parser, args):
    try:
        return ExecutionPolicy(args.execution, args.acknowledge_host_access)
    except ValueError as error:
        parser.error(str(error))


class NativeEnvironment:
    """Readiness reporting, not a sandbox or a container detector."""
    def __init__(self, root):
        self.root = root
        self.directory = root / '.runtime/native'

    def public(self):
        available = sys.platform == 'linux'
        return {'ready': available, 'available': available, 'installed': available,
                'busy': False, 'message': NATIVE_WARNING, 'error': '',
                'backend': 'Linux process / externally managed protection',
                'mode': 'native', 'isolated': False, 'memory_mb': None,
                'cpus': None, 'workspace_mb': None, 'network': 'inherited'}

    def verify(self):
        if sys.platform != 'linux':
            raise IsolationError('Native execution currently supports Linux only')
        if not (self.root / 'guest/worker.py').is_file():
            raise IsolationError('The native worker is missing')
        self.directory.mkdir(parents=True, exist_ok=True)

    def prepare(self):
        self.verify()
