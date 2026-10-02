import os
import re

from lado import state, tmux


def test_tests_ignore_the_lado_and_tmux_of_the_agent_running_them(lado_home):
    # An agent's shell has these set; `make check` must run there as is.
    for var in ("LADO_AGENT", "LADO_SESSION", "TMUX"):
        assert var not in os.environ
    assert state.home() == lado_home
    assert re.fullmatch(r"lado-test-[0-9a-f]{8}", tmux.socket())
