"""Point the Listener (and Persistent State's lock directory) at a temp root.

Every Listener test runs against its own runtime tree. Nothing under this
package's tests reads or writes the canonical inbox, Persistent State, Jira,
Supabase or a Product checkout.
"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.listener import store                     # noqa: E402
from agent.state import store as state_store         # noqa: E402


class IsolatedRuntime:
    """Redirect listener records and flock files into a throwaway directory."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="thebes-listener-test-")
        self._runtime = store.RUNTIME
        self._locks = state_store.LOCKS
        store.RUNTIME = os.path.join(self.dir, "listener-runtime")
        state_store.LOCKS = os.path.join(self.dir, "locks")
        return self

    def __exit__(self, *exc):
        store.RUNTIME = self._runtime
        state_store.LOCKS = self._locks
        shutil.rmtree(self.dir, ignore_errors=True)
        return False

    def simulate_restart(self):
        """Drop every in-memory handle. The records on disk are all that survive."""
        return store.read_intents()
