from eth2spec.test.context import (
    spec_state_test_with_matching_config,
    with_presets,
    with_light_client,
)
from eth2spec.test.helpers.attestations import (
    next_slots_with_attestations,
    state_transition_with_full_block,
)
from eth2spec.test.helpers.constants import (
    MINIMAL,
)
from eth2spec.test.helpers.light_client import (
    get_sync_aggregate,
    compute_start_slot_at_next_sync_committee_period,
)
from eth2spec.test.helpers.light_client_sync import (
    emit_force_update,
    emit_update,
    finish_lc_sync_test,
    setup_lc_sync_test,
)
from eth2spec.test.helpers.state import (
    next_slots,
    transition_to,
)


@with_light_client
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_light_client_sync(spec, state):
    # Start test
    test = yield from setup_lc_sync_test(spec, state)

    # Initial `LightClientUpdate`, populating `store.next_sync_committee`
    # ```
    #                                                                   |
    #    +-----------+                   +----------+     +-----------+ |
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature | |
    #    +-----------+                   +----------+     +-----------+ |
    #                                                                   |
    #                                                                   |
    #                                                            sync committee
    #                                                            period boundary
    # ```
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Advance to next sync committee period
    # ```
    #                                                                   |
    #    +-----------+                   +----------+     +-----------+ |
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature | |
    #    +-----------+                   +----------+     +-----------+ |
    #                                                                   |
    #                                                                   |
    #                                                            sync committee
    #                                                            period boundary
    # ```
    transition_to(spec, state, compute_start_slot_at_next_sync_committee_period(spec, state))
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Edge case: Signature in next period
    # ```
    #                                                  |
    #    +-----------+                   +----------+  |  +-----------+
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature |
    #    +-----------+                   +----------+  |  +-----------+
    #                                                  |
    #                                                  |
    #                                           sync committee
    #                                           period boundary
    # ```
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 2)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    transition_to(spec, state, compute_start_slot_at_next_sync_committee_period(spec, state))
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Edge case: Finalized header not included
    # ```
    #                          |
    #    + - - - - - +         |         +----------+     +-----------+
    #    ¦ finalized ¦ <-- (2 epochs) -- | attested | <-- | signature |
    #    + - - - - - +         |         +----------+     +-----------+
    #                          |
    #                          |
    #                   sync committee
    #                   period boundary
    # ```
    attested_block = block.copy()
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block=None)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Non-finalized case: Attested `next_sync_committee` is not finalized
    # ```
    #                          |
    #    +-----------+         |         +----------+     +-----------+
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature |
    #    +-----------+         |         +----------+     +-----------+
    #                          |
    #                          |
    #                   sync committee
    #                   period boundary
    # ```
    attested_block = block.copy()
    attested_state = state.copy()
    store_state = attested_state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Force-update using timeout
    # ```
    #                          |
    #    +-----------+         |         +----------+
    #    | finalized | <-- (2 epochs) -- | attested |
    #    +-----------+         |         +----------+
    #                          |            ^
    #                          |             \
    #                   sync committee        `--- store.finalized_header
    #                   period boundary
    # ```
    attested_block = block.copy()
    attested_state = state.copy()
    next_slots(spec, state, spec.UPDATE_TIMEOUT - 1)
    yield from emit_force_update(test, spec, state)
    assert test.store.finalized_header.beacon.slot == store_state.slot
    assert test.store.next_sync_committee == store_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == store_state.slot

    # Edge case: Finalized header not included, after force-update
    # ```
    #                          |                                |
    #    + - - - - - +         |         +--+     +----------+  |  +-----------+
    #    ¦ finalized ¦ <-- (2 epochs) -- |  | <-- | attested | <-- | signature |
    #    + - - - - - +         |         +--+     +----------+  |  +-----------+
    #                          |          /                     |
    #                          |  store.fin                     |
    #                   sync committee                   sync committee
    #                   period boundary                  period boundary
    # ```
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block=None)
    assert test.store.finalized_header.beacon.slot == store_state.slot
    assert test.store.next_sync_committee == store_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Edge case: Finalized header older than store
    # ```
    #                          |               |
    #    +-----------+         |         +--+  |  +----------+     +-----------+
    #    | finalized | <-- (2 epochs) -- |  | <-- | attested | <-- | signature |
    #    +-----------+         |         +--+  |  +----------+     +-----------+
    #                          |          /    |
    #                          |  store.fin    |
    #                   sync committee       sync committee
    #                   period boundary      period boundary
    # ```
    attested_block = block.copy()
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == store_state.slot
    assert test.store.next_sync_committee == store_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.store.optimistic_header.beacon.slot == attested_state.slot
    yield from emit_force_update(test, spec, state)
    assert test.store.finalized_header.beacon.slot == attested_state.slot
    assert test.store.next_sync_committee == attested_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Advance to next sync committee period
    # ```
    #                                                                   |
    #    +-----------+                   +----------+     +-----------+ |
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature | |
    #    +-----------+                   +----------+     +-----------+ |
    #                                                                   |
    #                                                                   |
    #                                                            sync committee
    #                                                            period boundary
    # ```
    transition_to(spec, state, compute_start_slot_at_next_sync_committee_period(spec, state))
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Finish test
    yield from finish_lc_sync_test(test)


@with_light_client
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_supply_sync_committee_from_past_update(spec, state):
    # Advance the chain, so that a `LightClientUpdate` from the past is available
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2 - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    past_state = state.copy()

    # Start test
    test = yield from setup_lc_sync_test(spec, state)
    assert not spec.is_next_sync_committee_known(test.store)

    # Apply `LightClientUpdate` from the past, populating `store.next_sync_committee`
    yield from emit_update(test, spec, past_state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == state.slot

    # Finish test
    yield from finish_lc_sync_test(test)


@with_light_client
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_advance_finality_without_sync_committee(spec, state):
    # Start test
    test = yield from setup_lc_sync_test(spec, state)

    # Initial `LightClientUpdate`, populating `store.next_sync_committee`
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Advance finality into next sync committee period, but omit `next_sync_committee`
    transition_to(spec, state, compute_start_slot_at_next_sync_committee_period(spec, state))
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, spec.SLOTS_PER_EPOCH - 1, True, True)
    justified_block = state_transition_with_full_block(spec, state, True, True)
    justified_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, with_next=False)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert not spec.is_next_sync_committee_known(test.store)
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Advance finality once more, with `next_sync_committee` still unknown
    past_state = finalized_state
    finalized_block = justified_block
    finalized_state = justified_state
    _, _, state = next_slots_with_attestations(spec, state, spec.SLOTS_PER_EPOCH - 2, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)

    # Apply `LightClientUpdate` without `finalized_header` nor `next_sync_committee`
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, None, with_next=False)
    assert test.store.finalized_header.beacon.slot == past_state.slot
    assert not spec.is_next_sync_committee_known(test.store)
    assert test.store.best_valid_update == update
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Apply `LightClientUpdate` with `finalized_header` but no `next_sync_committee`
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, with_next=False)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert not spec.is_next_sync_committee_known(test.store)
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Apply full `LightClientUpdate`, supplying `next_sync_committee`
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.store.finalized_header.beacon.slot == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.store.optimistic_header.beacon.slot == attested_state.slot

    # Finish test
    yield from finish_lc_sync_test(test)
