"""Fresh-VM continuation demonstration: resume a suffix on a new interpreter."""

from __future__ import annotations

import pytest

from malbolge_translator.fresh_vm_continuation import (
    FreshVMContinuationEvidence,
    run_fresh_vm_continuation,
    split_opcodes,
)

try:
    from malbolge import ProgramGenerator
    _MALBOLGE_AVAILABLE = True
except Exception:
    _MALBOLGE_AVAILABLE = False


def test_split_opcodes_rejects_edge_cases():
    assert split_opcodes("", None) == ("", "")
    with pytest.raises(ValueError):
        split_opcodes("abc", 0)
    with pytest.raises(ValueError):
        split_opcodes("abc", 3)


@pytest.mark.skipif(
    not _MALBOLGE_AVAILABLE,
    reason="malbolge-generator not installed; fresh-VM continuation not demonstrable",
)
def test_fresh_vm_continuation_hello_world():
    opcodes = ProgramGenerator().generate_for_string("Hello, World!").opcodes
    evidence = run_fresh_vm_continuation(opcodes)
    assert evidence.fresh_vm_continuation_pass
    assert evidence.concatenation_match
    # both halves actually participated in the output
    assert evidence.prefix_output != ""
    assert evidence.suffix_output != ""
    assert evidence.prefix_output + evidence.suffix_output == "Hello, World!"


@pytest.mark.skipif(
    not _MALBOLGE_AVAILABLE,
    reason="malbolge-generator not installed; fresh-VM continuation not demonstrable",
)
def test_fresh_vm_continuation_multilingual():
    opcodes = ProgramGenerator().generate_for_string("Hola mundo").opcodes
    evidence = run_fresh_vm_continuation(opcodes)
    assert evidence.fresh_vm_continuation_pass
    assert evidence.concatenated_output == "Hola mundo"


@pytest.mark.skipif(
    not _MALBOLGE_AVAILABLE,
    reason="malbolge-generator not installed; fresh-VM continuation not demonstrable",
)
def test_fresh_vm_continuation_short_word():
    opcodes = ProgramGenerator().generate_for_string("Hi").opcodes
    evidence = run_fresh_vm_continuation(opcodes)
    assert evidence.fresh_vm_continuation_pass
    assert evidence.concatenated_output == "Hi"


def test_evidence_to_dict_roundtrips():
    evidence = FreshVMContinuationEvidence()
    data = evidence.to_dict()
    assert data["fresh_vm_continuation_pass"] is False
    assert data["concatenation_match"] is False
    assert data["error"] is None