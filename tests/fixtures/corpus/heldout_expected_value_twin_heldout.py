# The held-out suite the source provides for heldout_expected_value_twin.
# The fixture encodes the hidden contract against the agent's changed
# behavior, so the known outcome is success: the change implements the
# documented addition contract the hidden suite pins.


def changed_add(a, b):
    """What the agent's change makes add() do."""
    return a + b


def test_hidden_add_contract():
    assert changed_add(2, 2) == 4
