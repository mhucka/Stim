# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import io
import pathlib
import tempfile
from typing import cast

import stim
import pytest
import numpy as np


def test_circuit_init_num_measurements_num_qubits():
    c = stim.Circuit()
    assert c.num_qubits == c.num_measurements == 0
    assert str(c).strip() == ""

    c.append_operation("X", [3])
    assert c.num_qubits == 4
    assert c.num_measurements == 0
    assert str(c).strip() == """
X 3
        """.strip()

    c.append_operation("M", [0])
    assert c.num_qubits == 4
    assert c.num_measurements == 1
    assert str(c).strip() == """
X 3
M 0
        """.strip()


def test_circuit_append_operation():
    c = stim.Circuit()

    with pytest.raises(IndexError, match="Gate not found"):
        c.append_operation("NOT_A_GATE", [0])
    with pytest.raises(ValueError, match="even number of targets"):
        c.append_operation("CNOT", [0])
    with pytest.raises(ValueError, match="takes 0"):
        c.append_operation("X", [0], 0.5)
    with pytest.raises(ValueError, match="invalid modifiers"):
        c.append_operation("X", [stim.target_inv(0)])
    with pytest.raises(ValueError, match="invalid modifiers"):
        c.append_operation("X", [stim.target_x(0)])
    with pytest.raises(IndexError, match="lookback"):
        stim.target_rec(0)
    with pytest.raises(IndexError, match="lookback"):
        stim.target_rec(1)
    with pytest.raises(IndexError, match="lookback"):
        stim.target_rec(-2**30)
    assert stim.target_rec(-1) is not None
    assert stim.target_rec(-15) is not None

    c.append_operation("X", [0])
    c.append_operation("X", [1, 2])
    c.append_operation("X", [3])
    c.append_operation("CNOT", [0, 1])
    c.append_operation("M", [0, stim.target_inv(1)])
    c.append_operation("X_ERROR", [0], 0.25)
    c.append_operation("CORRELATED_ERROR", [stim.target_x(0), stim.target_y(1)], 0.5)
    c.append_operation("DETECTOR", [stim.target_rec(-1)])
    c.append_operation("OBSERVABLE_INCLUDE", [stim.target_rec(-1), stim.target_rec(-2)], 5)
    assert str(c).strip() == """
X 0 1 2 3
CX 0 1
M 0 !1
X_ERROR(0.25) 0
E(0.5) X0 Y1
DETECTOR rec[-1]
OBSERVABLE_INCLUDE(5) rec[-1] rec[-2]
    """.strip()


def test_circuit_iadd():
    c = stim.Circuit()
    alias = c
    c.append_operation("X", [1, 2])
    c2 = stim.Circuit()
    c2.append_operation("Y", [3])
    c2.append_operation("M", [4])
    c += c2
    assert c is alias
    assert str(c).strip() == """
X 1 2
Y 3
M 4
        """.strip()

    c += c
    assert str(c).strip() == """
X 1 2
Y 3
M 4
X 1 2
Y 3
M 4
    """.strip()
    assert c is alias


def test_circuit_add():
    c = stim.Circuit()
    c.append_operation("X", [1, 2])
    c2 = stim.Circuit()
    c2.append_operation("Y", [3])
    c2.append_operation("M", [4])
    assert str(c + c2).strip() == """
X 1 2
Y 3
M 4
            """.strip()

    assert str(c2 + c2).strip() == """
Y 3
M 4
Y 3
M 4
        """.strip()


def test_circuit_mul():
    c = stim.Circuit()
    c.append_operation("Y", [3])
    c.append_operation("M", [4])
    assert str(c * 2) == str(2 * c) == """
REPEAT 2 {
    Y 3
    M 4
}
        """.strip()
    assert str((c * 2) * 3) == """
REPEAT 6 {
    Y 3
    M 4
}
        """.strip()
    expected = """
REPEAT 3 {
    Y 3
    M 4
}
    """.strip()
    assert str(c * 3) == str(3 * c) == expected
    alias = c
    c *= 3
    assert alias is c
    assert str(c) == expected
    c *= 1
    assert str(c) == expected
    assert alias is c
    c *= 0
    assert str(c) == ""
    assert alias is c


def test_circuit_repr():
    v = stim.Circuit("""
        X 0
        M 0
    """)
    r = repr(v)
    assert r == """stim.Circuit('''
    X 0
    M 0
''')"""
    assert eval(r, {'stim': stim}) == v


def test_circuit_eq():
    a = """
        X 0
        M 0
    """
    b = """
        Y 0
        M 0
    """
    assert stim.Circuit() == stim.Circuit()
    assert stim.Circuit() != stim.Circuit(a)
    assert not (stim.Circuit() != stim.Circuit())
    assert not (stim.Circuit() == stim.Circuit(a))
    assert stim.Circuit(a) == stim.Circuit(a)
    assert stim.Circuit(b) == stim.Circuit(b)
    assert stim.Circuit(a) != stim.Circuit(b)

    assert stim.Circuit() != None
    assert stim.Circuit != object()
    assert stim.Circuit != "another type"
    assert not (stim.Circuit == None)
    assert not (stim.Circuit == object())
    assert not (stim.Circuit == "another type")


def test_circuit_clear():
    c = stim.Circuit("""
        X 0
        M 0
    """)
    c.clear()
    assert c == stim.Circuit()


def test_circuit_compile_sampler():
    c = stim.Circuit()
    s = c.compile_sampler()
    c.append_operation("M", [0])
    assert repr(s) == "stim.CompiledMeasurementSampler(stim.Circuit())"
    s = c.compile_sampler()
    assert repr(s) == """
stim.CompiledMeasurementSampler(stim.Circuit('''
    M 0
'''))
    """.strip()

    c.append_operation("H", [0, 1, 2, 3, 4])
    c.append_operation("M", [0, 1, 2, 3, 4])
    s = c.compile_sampler()
    r = repr(s)
    assert r == """
stim.CompiledMeasurementSampler(stim.Circuit('''
    M 0
    H 0 1 2 3 4
    M 0 1 2 3 4
'''))
    """.strip() == str(stim.CompiledMeasurementSampler(c))

    # Check that expression can be evaluated.
    _ = eval(r, {"stim": stim})


def test_circuit_compile_detector_sampler():
    c = stim.Circuit()
    s = c.compile_detector_sampler()
    c.append_operation("M", [0])
    assert repr(s) == "stim.CompiledDetectorSampler(stim.Circuit())"
    c.append_operation("DETECTOR", [stim.target_rec(-1)])
    s = c.compile_detector_sampler()
    r = repr(s)
    assert r == """
stim.CompiledDetectorSampler(stim.Circuit('''
    M 0
    DETECTOR rec[-1]
'''))
    """.strip()

    # Check that expression can be evaluated.
    _ = eval(r, {"stim": stim})


def test_circuit_flattened_operations():
    assert stim.Circuit('''
        H 0
        REPEAT 3 {
            X_ERROR(0.125) 1
        }
        CORRELATED_ERROR(0.25) X3 Y4 Z5
        M 0 !1
        DETECTOR rec[-1]
    ''').flattened_operations() == [
        ("H", [0], 0),
        ("X_ERROR", [1], 0.125),
        ("X_ERROR", [1], 0.125),
        ("X_ERROR", [1], 0.125),
        ("E", [("X", 3), ("Y", 4), ("Z", 5)], 0.25),
        ("M", [0, ("inv", 1)], 0),
        ("DETECTOR", [("rec", -1)], 0),
    ]


def test_copy():
    c = stim.Circuit("H 0")
    c2 = c.copy()
    assert c == c2
    assert c is not c2


def test_hash():
    # stim.Circuit is mutable. It must not also be value-hashable.
    # Defining __hash__ requires defining a FrozenCircuit variant instead.
    with pytest.raises(TypeError, match="unhashable"):
        _ = hash(stim.Circuit())


def test_circuit_generation():
    surface_code_circuit = stim.Circuit.generated(
            "surface_code:rotated_memory_z",
            distance=5,
            rounds=10)
    samples = surface_code_circuit.compile_detector_sampler().sample(5)
    assert samples.shape == (5, 24 * 10)
    assert np.count_nonzero(samples) == 0


def test_circuit_generation_errors():
    with pytest.raises(ValueError, match="Known repetition_code tasks"):
        stim.Circuit.generated(
            "repetition_code:UNKNOWN",
            distance=3,
            rounds=1000)
    with pytest.raises(ValueError, match="Expected type to start with."):
        stim.Circuit.generated(
            "UNKNOWN:memory",
            distance=0,
            rounds=1000)
    with pytest.raises(ValueError, match="distance >= 2"):
        stim.Circuit.generated(
            "repetition_code:memory",
            distance=1,
            rounds=1000)

    with pytest.raises(ValueError, match="0 <= after_clifford_depolarization <= 1"):
        stim.Circuit.generated(
            "repetition_code:memory",
            distance=3,
            rounds=1000,
            after_clifford_depolarization=-1)
    with pytest.raises(ValueError, match="0 <= before_round_data_depolarization <= 1"):
        stim.Circuit.generated(
            "repetition_code:memory",
            distance=3,
            rounds=1000,
            before_round_data_depolarization=-1)
    with pytest.raises(ValueError, match="0 <= after_reset_flip_probability <= 1"):
        stim.Circuit.generated(
            "repetition_code:memory",
            distance=3,
            rounds=1000,
            after_reset_flip_probability=-1)
    with pytest.raises(ValueError, match="0 <= before_measure_flip_probability <= 1"):
        stim.Circuit.generated(
            "repetition_code:memory",
            distance=3,
            rounds=1000,
            before_measure_flip_probability=-1)


def test_num_detectors():
    assert stim.Circuit().num_detectors == 0
    assert stim.Circuit("DETECTOR").num_detectors == 1
    assert stim.Circuit("""
        REPEAT 1000 {
            DETECTOR
        }
    """).num_detectors == 1000
    assert stim.Circuit("""
        DETECTOR
        REPEAT 1000000 {
            REPEAT 1000000 {
                M 0
                DETECTOR rec[-1]
            }
        }
    """).num_detectors == 1000000**2 + 1


def test_num_observables():
    assert stim.Circuit().num_observables == 0
    assert stim.Circuit("OBSERVABLE_INCLUDE(0)").num_observables == 1
    assert stim.Circuit("OBSERVABLE_INCLUDE(1)").num_observables == 2
    assert stim.Circuit("""
        M 0
        OBSERVABLE_INCLUDE(2)
        REPEAT 1000000 {
            REPEAT 1000000 {
                M 0
                OBSERVABLE_INCLUDE(3) rec[-1]
            }
            OBSERVABLE_INCLUDE(4)
        }
    """).num_observables == 5


def test_indexing_operations():
    c = stim.Circuit()
    assert len(c) == 0
    assert list(c) == []
    with pytest.raises(IndexError):
        _ = c[0]
    with pytest.raises(IndexError):
        _ = c[-1]

    c = stim.Circuit('X 0')
    assert len(c) == 1
    assert list(c) == [stim.CircuitInstruction('X', [stim.GateTarget(0)])]
    assert c[0] == c[-1] == stim.CircuitInstruction('X', [stim.GateTarget(0)])
    with pytest.raises(IndexError):
        _ = c[1]
    with pytest.raises(IndexError):
        _ = c[-2]

    c = stim.Circuit('''
        X 5 6
        REPEAT 1000 {
            H 5
        }
        M !0
    ''')
    assert len(c) == 3
    with pytest.raises(IndexError):
        _ = c[3]
    with pytest.raises(IndexError):
        _ = c[-4]
    assert list(c) == [
        stim.CircuitInstruction('X', [stim.GateTarget(5), stim.GateTarget(6)]),
        stim.CircuitRepeatBlock(1000, stim.Circuit('H 5')),
        stim.CircuitInstruction('M', [stim.GateTarget(stim.target_inv(0))]),
    ]


def test_slicing():
    c = stim.Circuit("""
        H 0
        REPEAT 5 {
            X 1
        }
        Y 2
        Z 3
    """)
    assert c[:] is not c
    assert c[:] == c
    assert c[1:-1] == stim.Circuit("""
        REPEAT 5 {
            X 1
        }
        Y 2
    """)
    assert c[::2] == stim.Circuit("""
        H 0
        Y 2
    """)
    assert c[1::2] == stim.Circuit("""
        REPEAT 5 {
            X 1
        }
        Z 3
    """)


def test_reappend_gate_targets():
    expected = stim.Circuit("""
        MPP !X0 * X1
        CX rec[-1] 5
    """)
    c = stim.Circuit()
    c.append_operation("MPP", cast(stim.CircuitInstruction, expected[0]).targets_copy())
    c.append_operation("CX", cast(stim.CircuitInstruction, expected[1]).targets_copy())
    assert c == expected


def test_append_instructions_and_blocks():
    c = stim.Circuit()

    c.append_operation("TICK")
    assert c == stim.Circuit("TICK")

    with pytest.raises(ValueError, match="no targets"):
        c.append_operation("TICK", [1, 2, 3])

    c.append_operation(stim.Circuit("H 1")[0])
    assert c == stim.Circuit("TICK\nH 1")

    c.append_operation(stim.Circuit("CX 1 2 3 4")[0])
    assert c == stim.Circuit("""
        TICK
        H 1
        CX 1 2 3 4
    """)

    c.append_operation((stim.Circuit("X 5") * 100)[0])
    assert c == stim.Circuit("""
        TICK
        H 1
        CX 1 2 3 4
        REPEAT 100 {
            X 5
        }
    """)

    c.append_operation(stim.Circuit("PAULI_CHANNEL_1(0.125, 0.25, 0.325) 4 5 6")[0])
    assert c == stim.Circuit("""
        TICK
        H 1
        CX 1 2 3 4
        REPEAT 100 {
            X 5
        }
        PAULI_CHANNEL_1(0.125, 0.25, 0.325) 4 5 6
    """)

    with pytest.raises(ValueError, match="must be a"):
        c.append_operation(object())

    with pytest.raises(ValueError, match="targets"):
        c.append_operation(stim.Circuit("H 1")[0], [2])

    with pytest.raises(ValueError, match="arg"):
        c.append_operation(stim.Circuit("H 1")[0], [], 0.1)

    with pytest.raises(ValueError, match="targets"):
        c.append_operation((stim.Circuit("H 1") * 5)[0], [2])

    with pytest.raises(ValueError, match="arg"):
        c.append_operation((stim.Circuit("H 1") * 5)[0], [], 0.1)

    with pytest.raises(ValueError, match="repeat 0"):
        c.append_operation(stim.CircuitRepeatBlock(0, stim.Circuit("H 1")))


def test_circuit_measurement_sampling_seeded():
    c = stim.Circuit("""
        H 0
        M 0
    """)
    with pytest.raises(ValueError, match="seed"):
        c.compile_sampler(seed=-1)
    with pytest.raises(ValueError, match="seed"):
        c.compile_sampler(seed=object())

    s1 = c.compile_sampler().sample(256)
    s2 = c.compile_sampler().sample(256)
    assert not np.array_equal(s1, s2)

    s1 = c.compile_sampler(seed=None).sample(256)
    s2 = c.compile_sampler(seed=None).sample(256)
    assert not np.array_equal(s1, s2)

    s1 = c.compile_sampler(seed=5).sample(256)
    s2 = c.compile_sampler(seed=5).sample(256)
    s3 = c.compile_sampler(seed=6).sample(256)
    assert np.array_equal(s1, s2)
    assert not np.array_equal(s1, s3)


def test_circuit_detector_sampling_seeded():
    c = stim.Circuit("""
        X_ERROR(0.5) 0
        M 0
        DETECTOR rec[-1]
    """)
    with pytest.raises(ValueError, match="seed"):
        c.compile_detector_sampler(seed=-1)
    with pytest.raises(ValueError, match="seed"):
        c.compile_detector_sampler(seed=object())

    s1 = c.compile_detector_sampler().sample(256)
    s2 = c.compile_detector_sampler().sample(256)
    assert not np.array_equal(s1, s2)

    s1 = c.compile_detector_sampler(seed=None).sample(256)
    s2 = c.compile_detector_sampler(seed=None).sample(256)
    assert not np.array_equal(s1, s2)

    s1 = c.compile_detector_sampler(seed=5).sample(256)
    s2 = c.compile_detector_sampler(seed=5).sample(256)
    s3 = c.compile_detector_sampler(seed=6).sample(256)
    assert np.array_equal(s1, s2)
    assert not np.array_equal(s1, s3)


def test_approx_equals():
    base = stim.Circuit("X_ERROR(0.099) 0")
    assert not base.approx_equals(stim.Circuit("X_ERROR(0.101) 0"), atol=0)
    assert not base.approx_equals(stim.Circuit("X_ERROR(0.101) 0"), atol=0.00001)
    assert base.approx_equals(stim.Circuit("X_ERROR(0.101) 0"), atol=0.01)
    assert base.approx_equals(stim.Circuit("X_ERROR(0.101) 0"), atol=999)
    assert not base.approx_equals(stim.Circuit("DEPOLARIZE1(0.101) 0"), atol=999)

    assert not base.approx_equals(object(), atol=999)
    assert not base.approx_equals(stim.PauliString("XYZ"), atol=999)


def test_append_extended_cases():
    c = stim.Circuit()
    c.append("H", 5)
    c.append("CNOT", [0, 1])
    c.append("H", c[0].targets_copy()[0])
    c.append("X", (e + 1 for e in range(5)))
    assert c == stim.Circuit("""
        H 5
        CNOT 0 1
        H 5
        X 1 2 3 4 5
    """)


def test_pickle():
    import pickle

    t = stim.Circuit("""
        H 0
        REPEAT 100 {
            M 0
            CNOT rec[-1] 2
        }
    """)
    a = pickle.dumps(t)
    assert pickle.loads(a) == t


def test_backwards_compatibility_vs_safety_append_vs_append_operation():
    c = stim.Circuit()
    with pytest.raises(ValueError, match="takes 1 parens argument"):
        c.append("X_ERROR", [5])
    with pytest.raises(ValueError, match="takes 1 parens argument"):
        c.append("OBSERVABLE_INCLUDE", [])
    assert c == stim.Circuit()
    c.append_operation("X_ERROR", [5])
    assert c == stim.Circuit("X_ERROR(0) 5")
    c.append_operation("Z_ERROR", [5], 0.25)
    assert c == stim.Circuit("X_ERROR(0) 5\nZ_ERROR(0.25) 5")


def test_anti_commuting_mpp_error_message():
    with pytest.raises(ValueError, match="while analyzing a Pauli product measurement"):
        stim.Circuit("""
            MPP X0 Z0
            DETECTOR rec[-1]
        """).detector_error_model()


def test_blocked_remnant_edge_error():
    circuit = stim.Circuit("""
        X_ERROR(0.125) 0
        CORRELATED_ERROR(0.25) X0 X1
        M 0 1
        DETECTOR rec[-1]
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-2]
    """)

    assert circuit.detector_error_model(decompose_errors=True) == stim.DetectorErrorModel("""
        error(0.125) D2 D3
        error(0.25) D2 D3 ^ D0 D1
    """)

    with pytest.raises(ValueError, match="Failed to decompose"):
        circuit.detector_error_model(
            decompose_errors=True,
            block_decomposition_from_introducing_remnant_edges=True)

    assert circuit.detector_error_model(
        decompose_errors=True,
        block_decomposition_from_introducing_remnant_edges=True,
        ignore_decomposition_failures=True) == stim.DetectorErrorModel("""
            error(0.25) D0 D1 D2 D3
            error(0.125) D2 D3
        """)


def test_shortest_graphlike_error():
    c = stim.Circuit("""
        TICK
        X_ERROR(0.125) 0
        Y_ERROR(0.125) 0
        M 0
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)

    actual = c.shortest_graphlike_error()
    assert len(actual) == 1
    assert isinstance(actual[0], stim.ExplainedError)
    assert str(actual[0]) == """ExplainedError {
    dem_error_terms: L0
    CircuitErrorLocation {
        flipped_pauli_product: Y0
        Circuit location stack trace:
            (after 1 TICKs)
            at instruction #3 (Y_ERROR) in the circuit
            at target #1 of the instruction
            resolving to Y_ERROR(0.125) 0
    }
    CircuitErrorLocation {
        flipped_pauli_product: X0
        Circuit location stack trace:
            (after 1 TICKs)
            at instruction #2 (X_ERROR) in the circuit
            at target #1 of the instruction
            resolving to X_ERROR(0.125) 0
    }
}"""

    actual = c.shortest_graphlike_error(canonicalize_circuit_errors=True)
    assert len(actual) == 1
    assert isinstance(actual[0], stim.ExplainedError)
    assert str(actual[0]) == """ExplainedError {
    dem_error_terms: L0
    CircuitErrorLocation {
        flipped_pauli_product: X0
        Circuit location stack trace:
            (after 1 TICKs)
            at instruction #2 (X_ERROR) in the circuit
            at target #1 of the instruction
            resolving to X_ERROR(0.125) 0
    }
}"""


def test_shortest_graphlike_error_empty():
    with pytest.raises(ValueError, match="Failed to find"):
        stim.Circuit().shortest_graphlike_error()


def test_shortest_graphlike_error_msgs():
    with pytest.raises(
            ValueError,
            match="NO OBSERVABLES"
    ):
        stim.Circuit().shortest_graphlike_error()

    c = stim.Circuit("""
        M 0
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)
    with pytest.raises(ValueError, match="NO DETECTORS"):
        c.shortest_graphlike_error()

    c = stim.Circuit("""
        X_ERROR(0.1) 0
        M 0
    """)
    with pytest.raises(ValueError, match=r"NO OBSERVABLES(.|\n)*NO DETECTORS"):
        c.shortest_graphlike_error()
    with pytest.raises(ValueError, match=""):
        c.shortest_graphlike_error()

    c = stim.Circuit("""
        M 0
        DETECTOR rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)
    with pytest.raises(ValueError, match="NO ERRORS"):
        c.shortest_graphlike_error()

    c = stim.Circuit("""
        M(0.1) 0
        DETECTOR rec[-1]
        DETECTOR rec[-1]
        DETECTOR rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)
    with pytest.raises(ValueError, match="NO GRAPHLIKE ERRORS"):
        c.shortest_graphlike_error()

    c = stim.Circuit("""
        X_ERROR(0.1) 0
        M 0
        DETECTOR rec[-1]
    """)
    with pytest.raises(ValueError, match="NO OBSERVABLES"):
        c.shortest_graphlike_error()


def test_search_for_undetectable_logical_errors_empty():
    with pytest.raises(ValueError, match="Failed to find"):
        stim.Circuit().search_for_undetectable_logical_errors(
            dont_explore_edges_increasing_symptom_degree=True,
            dont_explore_edges_with_degree_above=4,
            dont_explore_detection_event_sets_with_size_above=4,
        )


def test_search_for_undetectable_logical_errors_msgs():
    with pytest.raises(ValueError, match=r"NO OBSERVABLES(.|\n)*NO DETECTORS"):
        stim.Circuit().search_for_undetectable_logical_errors(
            dont_explore_edges_increasing_symptom_degree=True,
            dont_explore_edges_with_degree_above=4,
            dont_explore_detection_event_sets_with_size_above=4,
        )

    c = stim.Circuit("""
        M 0
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)
    with pytest.raises(ValueError, match=r"NO DETECTORS(.|\n)*NO ERRORS"):
        c.search_for_undetectable_logical_errors(
            dont_explore_edges_increasing_symptom_degree=True,
            dont_explore_edges_with_degree_above=4,
            dont_explore_detection_event_sets_with_size_above=4,
        )

    c = stim.Circuit("""
        X_ERROR(0.1) 0
        M 0
    """)
    with pytest.raises(ValueError, match=r"NO OBSERVABLES(.|\n)*NO DETECTORS(.|\n)*NO ERRORS"):
        c.search_for_undetectable_logical_errors(
            dont_explore_edges_increasing_symptom_degree=True,
            dont_explore_edges_with_degree_above=4,
            dont_explore_detection_event_sets_with_size_above=4,
        )

    c = stim.Circuit("""
        M 0
        DETECTOR rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)
    with pytest.raises(ValueError, match="NO ERRORS"):
        c.search_for_undetectable_logical_errors(
            dont_explore_edges_increasing_symptom_degree=True,
            dont_explore_edges_with_degree_above=4,
            dont_explore_detection_event_sets_with_size_above=4,
        )

    c = stim.Circuit("""
        X_ERROR(0.1) 0
        M 0
        DETECTOR rec[-1]
    """)
    with pytest.raises(ValueError, match="NO OBSERVABLES"):
        c.search_for_undetectable_logical_errors(
            dont_explore_edges_increasing_symptom_degree=True,
            dont_explore_edges_with_degree_above=4,
            dont_explore_detection_event_sets_with_size_above=4,
        )


def test_shortest_error_sat_problem_unrecognized_format():
    c = stim.Circuit("""
        X_ERROR(0.1) 0
        M 0
        OBSERVABLE_INCLUDE(0) rec[-1]
        X_ERROR(0.4) 0
        M 0
        DETECTOR rec[-1] rec[-2]
    """)
    with pytest.raises(ValueError, match='Unsupported format'):
        _ = c.shortest_error_sat_problem(format='unsupported format name')


def test_shortest_error_sat_problem():
    c = stim.Circuit("""
        X_ERROR(0.1) 0
        M 0
        OBSERVABLE_INCLUDE(0) rec[-1]
        X_ERROR(0.4) 0
        M 0
        DETECTOR rec[-1] rec[-2]
    """)
    sat_str = c.shortest_error_sat_problem()
    assert sat_str == 'p wcnf 2 4 5\n1 -1 0\n1 -2 0\n5 -1 0\n5 2 0\n'


def test_likeliest_error_sat_problem():
    c = stim.Circuit("""
        X_ERROR(0.1) 0
        M 0
        OBSERVABLE_INCLUDE(0) rec[-1]
        X_ERROR(0.4) 0
        M 0
        DETECTOR rec[-1] rec[-2]
    """)
    sat_str = c.likeliest_error_sat_problem(quantization=100)
    assert sat_str == 'p wcnf 2 4 401\n18 -1 0\n100 -2 0\n401 -1 0\n401 2 0\n'


def test_shortest_graphlike_error_ignore():
    c = stim.Circuit("""
        TICK
        X_ERROR(0.125) 0
        M 0
        DETECTOR rec[-1]
        DETECTOR rec[-1]
        DETECTOR rec[-1]
    """)
    with pytest.raises(ValueError, match="Failed to decompose errors"):
        c.shortest_graphlike_error(ignore_ungraphlike_errors=False)
    with pytest.raises(ValueError, match="Failed to find any graphlike logical errors"):
        c.shortest_graphlike_error(ignore_ungraphlike_errors=True)


def test_coords():
    circuit = stim.Circuit("""
        QUBIT_COORDS(1, 2, 3) 0
        QUBIT_COORDS(2) 1
        SHIFT_COORDS(5)
        QUBIT_COORDS(3) 4
    """)
    assert circuit.get_final_qubit_coordinates() == {
        0: [1, 2, 3],
        1: [2],
        4: [8],
    }


def test_explain_errors():
    circuit = stim.Circuit("""
        H 0
        CNOT 0 1
        DEPOLARIZE1(0.01) 0
        CNOT 0 1
        H 0
        M 0 1
        DETECTOR rec[-1]
        DETECTOR rec[-2]
    """)
    r = circuit.explain_detector_error_model_errors()
    assert len(r) == 3
    assert str(r[0]) == """ExplainedError {
    dem_error_terms: D0
    CircuitErrorLocation {
        flipped_pauli_product: X0
        Circuit location stack trace:
            (after 0 TICKs)
            at instruction #3 (DEPOLARIZE1) in the circuit
            at target #1 of the instruction
            resolving to DEPOLARIZE1(0.01) 0
    }
}"""
    assert str(r[1]) == """ExplainedError {
    dem_error_terms: D0 D1
    CircuitErrorLocation {
        flipped_pauli_product: Y0
        Circuit location stack trace:
            (after 0 TICKs)
            at instruction #3 (DEPOLARIZE1) in the circuit
            at target #1 of the instruction
            resolving to DEPOLARIZE1(0.01) 0
    }
}"""
    assert str(r[2]) == """ExplainedError {
    dem_error_terms: D1
    CircuitErrorLocation {
        flipped_pauli_product: Z0
        Circuit location stack trace:
            (after 0 TICKs)
            at instruction #3 (DEPOLARIZE1) in the circuit
            at target #1 of the instruction
            resolving to DEPOLARIZE1(0.01) 0
    }
}"""

    r = circuit.explain_detector_error_model_errors(
        dem_filter=stim.DetectorErrorModel('error(1) D0 D1'),
        reduce_to_one_representative_error=True,
    )
    assert len(r) == 1
    assert str(r[0]) == """ExplainedError {
    dem_error_terms: D0 D1
    CircuitErrorLocation {
        flipped_pauli_product: Y0
        Circuit location stack trace:
            (after 0 TICKs)
            at instruction #3 (DEPOLARIZE1) in the circuit
            at target #1 of the instruction
            resolving to DEPOLARIZE1(0.01) 0
    }
}"""


def test_without_noise():
    assert stim.Circuit("""
        X_ERROR(0.25) 0
        CNOT 0 1
        M(0.125) 0
        REPEAT 50 {
            DEPOLARIZE1(0.25) 0 1 2
            X 0 1 2
        }
    """).without_noise() == stim.Circuit("""
        CNOT 0 1
        M 0
        REPEAT 50 {
            X 0 1 2
        }
    """)


def test_flattened():
    assert stim.Circuit("""
        SHIFT_COORDS(5, 0)
        QUBIT_COORDS(1, 2, 3) 0
        REPEAT 5 {
            MR 0 1
            DETECTOR(0, 0) rec[-2]
            DETECTOR(1, 0) rec[-1]
            SHIFT_COORDS(0, 1)
        }
    """).flattened() == stim.Circuit("""
        QUBIT_COORDS(6, 2, 3) 0
        MR 0 1
        DETECTOR(5, 0) rec[-2]
        DETECTOR(6, 0) rec[-1]
        MR 0 1
        DETECTOR(5, 1) rec[-2]
        DETECTOR(6, 1) rec[-1]
        MR 0 1
        DETECTOR(5, 2) rec[-2]
        DETECTOR(6, 2) rec[-1]
        MR 0 1
        DETECTOR(5, 3) rec[-2]
        DETECTOR(6, 3) rec[-1]
        MR 0 1
        DETECTOR(5, 4) rec[-2]
        DETECTOR(6, 4) rec[-1]
    """)


def test_complex_slice_does_not_seg_fault():
    with pytest.raises(TypeError):
        _ = stim.Circuit()[1j]


def test_circuit_from_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = tmpdir + '/tmp.stim'
        with open(path, 'w') as f:
            print('H 5', file=f)
        assert stim.Circuit.from_file(path) == stim.Circuit('H 5')

    with tempfile.TemporaryDirectory() as tmpdir:
        path = pathlib.Path(tmpdir) / 'tmp.stim'
        with open(path, 'w') as f:
            print('H 5', file=f)
        assert stim.Circuit.from_file(path) == stim.Circuit('H 5')

    with tempfile.TemporaryDirectory() as tmpdir:
        path = tmpdir + '/tmp.stim'
        with open(path, 'w') as f:
            print('CNOT 4 5', file=f)
        with open(path) as f:
            assert stim.Circuit.from_file(f) == stim.Circuit('CX 4 5')

    with pytest.raises(ValueError, match="how to read"):
        stim.Circuit.from_file(object())
    with pytest.raises(ValueError, match="how to read"):
        stim.Circuit.from_file(123)


def test_circuit_to_file():
    c = stim.Circuit('H 5\ncnot 0 1')
    with tempfile.TemporaryDirectory() as tmpdir:
        path = tmpdir + '/tmp.stim'
        c.to_file(path)
        with open(path) as f:
            assert f.read() == 'H 5\nCX 0 1\n'

    with tempfile.TemporaryDirectory() as tmpdir:
        path = pathlib.Path(tmpdir) / 'tmp.stim'
        c.to_file(path)
        with open(path) as f:
            assert f.read() == 'H 5\nCX 0 1\n'

    with tempfile.TemporaryDirectory() as tmpdir:
        path = tmpdir + '/tmp.stim'
        with open(path, 'w') as f:
            c.to_file(f)
        with open(path) as f:
            assert f.read() == 'H 5\nCX 0 1\n'

    with pytest.raises(ValueError, match="how to write"):
        c.to_file(object())
    with pytest.raises(ValueError, match="how to write"):
        c.to_file(123)


def test_diagram():
    c = stim.Circuit("""
        H 0
        CX 0 1
    """)
    assert str(c.diagram()).strip() == """
q0: -H-@-
       |
q1: ---X-
    """.strip()
    assert str(c.diagram(type='timeline-text')) == str(c.diagram())

    c = stim.Circuit("""
        H 0
        CNOT 0 1
        TICK
        M 0 1
        DETECTOR rec[-1] rec[-2]
    """)
    assert str(c.diagram(type='detector-slice-text', tick=1)).strip() == """
q0: -Z:D0-
     |
q1: -Z:D0-
    """.strip()

    c = stim.Circuit("""
        H 0
        CNOT 0 1 0 2
        TICK
        M 0 1 2
        DETECTOR(4,5) rec[-1] rec[-2]
        DETECTOR(6) rec[-2] rec[-3]
    """)
    assert str(c.diagram(type='detector-slice-text', tick=1, filter_coords=[(5, 6, 7), (6,), (7, 8)])).strip() == """
q0: -Z:D1-
     |
q1: -Z:D1-

q2: ------
    """.strip()

    assert c.diagram() is not None
    assert c.diagram(type="timeline-svg") is not None
    assert c.diagram(type="timeline-svg", tick=5) is not None
    assert c.diagram("timeline-svg") is not None
    assert c.diagram("timeline-3d") is not None
    assert c.diagram("timeline-3d-html") is not None

    assert c.diagram("matchgraph-svg") is not None
    assert c.diagram("matchgraph-3d") is not None
    assert c.diagram("matchgraph-3d-html") is not None
    assert c.diagram("match-graph-svg") is not None
    assert c.diagram("match-graph-3d") is not None
    assert c.diagram("match-graph-3d-html") is not None

    assert c.diagram("detslice-svg", tick=1) is not None
    assert c.diagram("detslice-text", tick=1) is not None
    assert c.diagram("detector-slice-svg", tick=1) is not None
    assert c.diagram("detector-slice-text", tick=1) is not None

    assert c.diagram("detslice-with-ops-svg", tick=1) is not None
    assert c.diagram("timeslice-svg", tick=1) is not None
    assert c.diagram("time-slice-svg", tick=1) is not None
    assert c.diagram("time+detector-slice-svg", tick=1) is not None
    assert c.diagram("time+detector-slice-svg", tick=range(1, 3)) is not None
    with pytest.raises(ValueError, match="step"):
        assert c.diagram("time+detector-slice-svg", tick=range(1, 3, 2)) is not None
    with pytest.raises(ValueError, match="stop"):
        assert c.diagram("time+detector-slice-svg", tick=range(3, 3)) is not None
    assert "iframe" in str(c.diagram(type="match-graph-svg-html"))
    assert "iframe" in str(c.diagram(type="detslice-svg-html"))
    assert "iframe" in str(c.diagram(type="timeslice-svg-html"))
    assert "iframe" in str(c.diagram(type="timeline-svg-html"))


def test_circuit_inverse():
    assert stim.Circuit("""
        S 0 1
        CX 0 1 0 2
    """).inverse() == stim.Circuit("""
        CX 0 2 0 1
        S_DAG 1 0
    """)


def test_circuit_slice_reverse():
    c = stim.Circuit()
    assert c[::-1] == stim.Circuit()
    c = stim.Circuit("X 1\nY 2\nZ 3")
    assert c[::-1] == stim.Circuit("Z 3\nY 2\nX 1")


def test_with_inlined_feedback_bad_end_eats_into_loop():
    assert stim.Circuit("""
        CX 0 1
        M 1
        CX rec[-1] 1
        CX 0 1
        M 1
        DETECTOR rec[-1] rec[-2]
        OBSERVABLE_INCLUDE(0) rec[-1]
    """).with_inlined_feedback() == stim.Circuit("""
        CX 0 1
        M 1
        OBSERVABLE_INCLUDE(0) rec[-1]
        CX 0 1
        M 1
        DETECTOR rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)

    before = stim.Circuit("""
        R 0 1 2 3 4 5 6

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        CX rec[-1] 5 rec[-2] 3 rec[-3] 1
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-3]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        REPEAT 10 {
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            CX 0 1 2 3 4 5
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            CX 6 5 4 3 2 1
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            M(0.25) 1 3 5
            CX rec[-1] 5 rec[-2] 3 rec[-3] 1
            DETECTOR rec[-1] rec[-4]
            DETECTOR rec[-2] rec[-5]
            DETECTOR rec[-3] rec[-6]
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
        }

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        CX rec[-1] 5 rec[-2] 3 rec[-3] 1
        DETECTOR rec[-1] rec[-2] rec[-3]
        DETECTOR rec[-3] rec[-4] rec[-5]
        DETECTOR rec[-5] rec[-6] rec[-7]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        OBSERVABLE_INCLUDE(0) rec[-1]
    """)
    after = before.with_inlined_feedback()
    assert after == stim.Circuit("""
        R 0 1 2 3 4 5 6

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-3]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-3]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        REPEAT 8 {
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            CX 0 1 2 3 4 5
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            CX 6 5 4 3 2 1
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            M(0.25) 1 3 5
            DETECTOR rec[-7] rec[-1]
            DETECTOR rec[-8] rec[-2]
            DETECTOR rec[-9] rec[-3]
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
        }

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        OBSERVABLE_INCLUDE(0) rec[-1]
        DETECTOR rec[-7] rec[-1]
        DETECTOR rec[-8] rec[-2]
        DETECTOR rec[-9] rec[-3]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        DETECTOR rec[-6] rec[-5] rec[-4] rec[-3] rec[-2] rec[-1]
        DETECTOR rec[-8] rec[-7] rec[-6] rec[-5] rec[-4] rec[-3]
        DETECTOR rec[-10] rec[-9] rec[-8] rec[-7] rec[-6] rec[-5]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        OBSERVABLE_INCLUDE(0) rec[-1]
    """)

    dem1 = before.flattened().detector_error_model()
    dem2 = after.flattened().detector_error_model()
    assert dem1.approx_equals(dem2, atol=1e-5)


def test_with_inlined_feedback():
    assert stim.Circuit("""
        CX 0 1
        M 1
        CX rec[-1] 1
        CX 0 1
        M 1
        DETECTOR rec[-1] rec[-2]
        OBSERVABLE_INCLUDE(0) rec[-1]
    """).with_inlined_feedback() == stim.Circuit("""
        CX 0 1
        M 1
        OBSERVABLE_INCLUDE(0) rec[-1]
        CX 0 1
        M 1
        DETECTOR rec[-1]
        OBSERVABLE_INCLUDE(0) rec[-1]
    """)

    before = stim.Circuit("""
        R 0 1 2 3 4 5 6

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        CX rec[-1] 5 rec[-2] 3 rec[-3] 1
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-3]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        REPEAT 10 {
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            CX 0 1 2 3 4 5
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            CX 6 5 4 3 2 1
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            M(0.25) 1 3 5
            CX rec[-1] 5 rec[-2] 3 rec[-3] 1
            DETECTOR rec[-1] rec[-4]
            DETECTOR rec[-2] rec[-5]
            DETECTOR rec[-3] rec[-6]
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
        }

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 0 1 2 3 4 5 6
        CX rec[-1] 5 rec[-2] 3 rec[-3] 1
        DETECTOR rec[-1] rec[-2] rec[-3]
        DETECTOR rec[-3] rec[-4] rec[-5]
        DETECTOR rec[-5] rec[-6] rec[-7]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        OBSERVABLE_INCLUDE(0) rec[-1]
    """)
    after = before.with_inlined_feedback()
    assert str(after) == str(stim.Circuit("""
        R 0 1 2 3 4 5 6

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-3]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 1 3 5
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-3]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        REPEAT 9 {
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            CX 0 1 2 3 4 5
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            CX 6 5 4 3 2 1
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
            M(0.25) 1 3 5
            DETECTOR rec[-7] rec[-1]
            DETECTOR rec[-8] rec[-2]
            DETECTOR rec[-9] rec[-3]
            X_ERROR(0.125) 0 1 2 3 4 5 6
            TICK
        }

        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 0 1 2 3 4 5
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        CX 6 5 4 3 2 1
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK
        M(0.25) 0 1 2 3 4 5 6
        DETECTOR rec[-8] rec[-3] rec[-2] rec[-1]
        DETECTOR rec[-9] rec[-5] rec[-4] rec[-3]
        DETECTOR rec[-10] rec[-7] rec[-6] rec[-5]
        X_ERROR(0.125) 0 1 2 3 4 5 6
        TICK

        OBSERVABLE_INCLUDE(0) rec[-1]
    """))

    dem1 = before.flattened().detector_error_model()
    dem2 = after.flattened().detector_error_model()
    assert dem1.approx_equals(dem2, atol=1e-5)


def test_detslice_ops_diagram_no_ticks_does_not_hang():
    assert stim.Circuit.generated("surface_code:rotated_memory_x", rounds=5, distance=5).diagram("detslice-svg") is not None


def test_num_ticks():
    assert stim.Circuit().num_ticks == 0
    assert stim.Circuit("TICK").num_ticks == 1
    assert stim.Circuit("""
        TICK
        REPEAT 100 {
            TICK
            TICK
            REPEAT 10 {
                TICK
            }
        }
    """).num_ticks == 1201
    assert stim.Circuit("""
        H 0
        TICK
        CX 0 1
        TICK
    """).num_ticks == 2


def test_reference_sample():
    circuit = stim.Circuit(
        """
        H 0
        CNOT 0 1
    """
    )
    ref = circuit.reference_sample()
    assert len(ref) == 0
    circuit = stim.Circuit(
        """
        H 0 1
        CX 0 2 1 3
        MPP X0*X1 Y0*Y1 Z0*Z1
        """
    )
    np.testing.assert_array_equal(circuit.reference_sample(), circuit.reference_sample())
    assert np.sum(circuit.reference_sample()) % 2 == 1
    circuit.append("X", (i for i in range(0, 100, 2)))
    circuit.append("M", (i for i in range(100)))
    ref_sample = circuit.reference_sample(bit_packed=True)
    unpacked = np.unpackbits(ref_sample, bitorder="little")
    expected = circuit.reference_sample(bit_packed=False)
    expected_padded = np.zeros_like(unpacked)
    expected_padded[:len(expected)] = expected
    np.testing.assert_array_equal(unpacked, expected_padded)


def test_max_mix_depolarization_is_allowed_in_dem_conversion_without_args():
    assert stim.Circuit("""
        H 0
        CX 0 1
        DEPOLARIZE1(0.75) 0
        CX 0 1
        H 0
        M 0 1
        DETECTOR rec[-1]
        DETECTOR rec[-2]
    """).detector_error_model(approximate_disjoint_errors=True) == stim.DetectorErrorModel("""
        error(0.5) D0
        error(0.5) D0 D1
        error(0.5) D1
    """)

    assert stim.Circuit("""
        H 0 1
        CX 0 2 1 3
        DEPOLARIZE2(0.9375) 0 1
        CX 0 2 1 3
        H 0 1
        M 0 1 2 3
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        DETECTOR rec[-3]
        DETECTOR rec[-4]
    """).detector_error_model() == stim.DetectorErrorModel("""
        error(0.5) D0
        error(0.5) D0 D1
        error(0.5) D0 D1 D2
        error(0.5) D0 D1 D2 D3
        error(0.5) D0 D1 D3
        error(0.5) D0 D2
        error(0.5) D0 D2 D3
        error(0.5) D0 D3
        error(0.5) D1
        error(0.5) D1 D2
        error(0.5) D1 D2 D3
        error(0.5) D1 D3
        error(0.5) D2
        error(0.5) D2 D3
        error(0.5) D3
    """)


def test_shortest_graphlike_error_many_obs():
    c = stim.Circuit("""
        MPP Z0*Z1 Z1*Z2 Z2*Z3 Z3*Z4
        X_ERROR(0.1) 0 1 2 3 4
        MPP Z0*Z1 Z1*Z2 Z2*Z3 Z3*Z4
        DETECTOR rec[-1] rec[-5]
        DETECTOR rec[-2] rec[-6]
        DETECTOR rec[-3] rec[-7]
        DETECTOR rec[-4] rec[-8]
        M 4
        OBSERVABLE_INCLUDE(1200) rec[-1]
    """)
    assert len(c.shortest_graphlike_error()) == 5


def test_detslice_filter_coords_flexibility():
    c = stim.Circuit.generated("repetition_code:memory", distance=3, rounds=3)
    d1 = c.diagram("detslice", filter_coords=[stim.DemTarget.relative_detector_id(1)])
    d2 = c.diagram("detslice-svg", filter_coords=stim.DemTarget.relative_detector_id(1))
    d3 = c.diagram("detslice", filter_coords=["D1"])
    d4 = c.diagram("detslice", filter_coords="D1")
    d5 = c.diagram("detector-slice-svg", filter_coords=[3, 0])
    d6 = c.diagram("detslice-svg", filter_coords=[[3, 0]])
    assert str(d1) == str(d2)
    assert str(d1) == str(d3)
    assert str(d1) == str(d4)
    assert str(d1) == str(d5)
    assert str(d1) == str(d6)
    assert str(d1) != str(c.diagram("detslice", filter_coords="L0"))

    d1 = c.diagram("detslice", filter_coords=[stim.DemTarget.relative_detector_id(1), stim.DemTarget.relative_detector_id(3), stim.DemTarget.relative_detector_id(5), "D7"])
    d2 = c.diagram("detslice", filter_coords=["D1", "D3", "D5", "D7"])
    d3 = c.diagram("detslice-svg", filter_coords=[3,])
    d4 = c.diagram("detslice-svg", filter_coords=[[3,]])
    d5 = c.diagram("detslice-svg", filter_coords=[[3, 0], [3, 1], [3, 2], [3, 3]])
    assert str(d1) == str(d2)
    assert str(d1) == str(d3)
    assert str(d1) == str(d4)
    assert str(d1) == str(d5)


def test_has_flow_ry():
    c = stim.Circuit("""
        RY 0
    """)
    assert c.has_flow(stim.Flow("1 -> Y"))
    assert not c.has_flow(stim.Flow("1 -> -Y"))
    assert not c.has_flow(stim.Flow("1 -> X"))
    assert c.has_flow(stim.Flow("1 -> Y"), unsigned=True)
    assert not c.has_flow(stim.Flow("1 -> X"), unsigned=True)
    assert c.has_flow(stim.Flow("1 -> -Y"), unsigned=True)


def test_has_flow_cxs():
    c = stim.Circuit("""
        CX 0 1
        S 0
    """)

    assert c.has_flow(stim.Flow("X_ -> YX"))
    assert c.has_flow(stim.Flow("Y_ -> -XX"))
    assert not c.has_flow(stim.Flow("X_ -> XX"))
    assert not c.has_flow(stim.Flow("X_ -> -XX"))

    assert c.has_flow(stim.Flow("X_ -> YX"), unsigned=True)
    assert c.has_flow(stim.Flow("Y_ -> -XX"), unsigned=True)
    assert not c.has_flow(stim.Flow("X_ -> XX"), unsigned=True)
    assert not c.has_flow(stim.Flow("X_ -> -XX"), unsigned=True)


def test_has_flow_cxm():
    c = stim.Circuit("""
        CX 0 1
        M 1
    """)
    assert c.has_flow(stim.Flow("1 -> _Z xor rec[0]"))
    assert c.has_flow(stim.Flow("ZZ -> rec[0]"))
    assert c.has_flow(stim.Flow("ZZ -> _Z"))
    assert c.has_flow(stim.Flow("XX -> X_"))
    assert c.has_flow(stim.Flow("1 -> _Z xor rec[0]"), unsigned=True)
    assert c.has_flow(stim.Flow("ZZ -> rec[0]"), unsigned=True)
    assert c.has_flow(stim.Flow("ZZ -> _Z"), unsigned=True)
    assert c.has_flow(stim.Flow("XX -> X_"), unsigned=True)


def test_has_flow_lattice_surgery():
    c = stim.Circuit("""
        # Lattice surgery CNOT with feedback.
        RX 2
        MZZ 2 0
        MXX 2 1
        MZ 2
        CX rec[-1] 1 rec[-3] 1
        CZ rec[-2] 0

        S 0
    """)
    assert c.has_flow(stim.Flow("X_ -> YX"))
    assert c.has_flow(stim.Flow("Z_ -> Z_"))
    assert c.has_flow(stim.Flow("_X -> _X"))
    assert c.has_flow(stim.Flow("_Z -> ZZ"))
    assert not c.has_flow(stim.Flow("X_ -> XX"))

    assert not c.has_flow(stim.Flow("X_ -> XX"))
    assert not c.has_flow(stim.Flow("X_ -> -YX"))
    assert not c.has_flow(stim.Flow("X_ -> XX"), unsigned=True)
    assert c.has_flow(stim.Flow("X_ -> -YX"), unsigned=True)


def test_has_flow_lattice_surgery_without_feedback():
    c = stim.Circuit("""
        # Lattice surgery CNOT without feedback.
        RX 2
        MZZ 2 0
        MXX 2 1
        MZ 2

        S 0
    """)
    assert c.has_flow(stim.Flow("X_ -> YX xor rec[1]"))
    assert c.has_flow(stim.Flow("Z_ -> Z_"))
    assert c.has_flow(stim.Flow("_X -> _X"))
    assert c.has_flow(stim.Flow("_Z -> ZZ xor rec[0] xor rec[2]"))
    assert not c.has_flow(stim.Flow("X_ -> XX"))
    assert c.has_all_flows([])
    assert c.has_all_flows([
        stim.Flow("X_ -> YX xor rec[1]"),
        stim.Flow("Z_ -> Z_"),
    ])
    assert not c.has_all_flows([
        stim.Flow("X_ -> YX xor rec[1]"),
        stim.Flow("Z_ -> Z_"),
        stim.Flow("X_ -> XX"),
    ])

    assert not c.has_flow(stim.Flow("X_ -> XX"))
    assert not c.has_flow(stim.Flow("X_ -> -YX"))
    assert not c.has_flow(stim.Flow("X_ -> XX"), unsigned=True)
    assert c.has_flow(stim.Flow("X_ -> -YX xor rec[1]"), unsigned=True)


def test_has_flow_shorthands():
    c = stim.Circuit("""
        MZ 99
        MXX 1 99
        MZZ 0 99
        MX 99
    """)

    assert c.has_flow(stim.Flow("X_ -> XX xor rec[1] xor rec[3]"))
    assert c.has_flow(stim.Flow("Z_ -> Z_"))
    assert c.has_flow(stim.Flow("_X -> _X"))
    assert c.has_flow(stim.Flow("_Z -> ZZ xor rec[0] xor rec[2]"))

    assert c.has_flow(stim.Flow("X_ -> XX xor rec[1] xor rec[3]"))
    assert not c.has_flow(stim.Flow("Z_ -> -Z_"))
    assert not c.has_flow(stim.Flow("-Z_ -> Z_"))
    assert not c.has_flow(stim.Flow("Z_ -> X_"))
    assert c.has_flow(stim.Flow("iX_ -> iXX xor rec[1] xor rec[3]"))
    assert not c.has_flow(stim.Flow("-iX_ -> iXX xor rec[1] xor rec[3]"))
    assert c.has_flow(stim.Flow("-iX_ -> -iXX xor rec[1] xor rec[3]"))
    with pytest.raises(ValueError, match="Anti-Hermitian"):
        stim.Flow("iX_ -> XX")


def test_decomposed():
    assert stim.Circuit("""
        ISWAP 0 1 2 1
        TICK
        MPP X1*Z2*Y3
    """).decomposed() == stim.Circuit("""
        H 0
        CX 0 1 1 0
        H 1
        S 1 0
        H 2
        CX 2 1 1 2
        H 1
        S 1 2
        TICK
        H 1 3
        S 3
        H 3
        S 3 3
        CX 2 1 3 1
        M 1
        CX 2 1 3 1
        H 3
        S 3
        H 3
        S 3 3
        H 1
    """)


def test_detecting_regions():
    assert stim.Circuit('''
        R 0
        TICK
        H 0
        TICK
        CX 0 1
        TICK
        MX 0 1
        DETECTOR rec[-1] rec[-2]
    ''').detecting_regions() == {stim.DemTarget.relative_detector_id(0): {
        0: stim.PauliString("Z_"),
        1: stim.PauliString("X_"),
        2: stim.PauliString("XX"),
    }}


def test_detecting_region_filters():
    c = stim.Circuit.generated("repetition_code:memory", distance=3, rounds=3)
    assert len(c.detecting_regions(targets=["D"])) == c.num_detectors
    assert len(c.detecting_regions(targets=["L"])) == c.num_observables
    assert len(c.detecting_regions()) == c.num_observables + c.num_detectors
    assert len(c.detecting_regions(targets=["D0"])) == 1
    assert len(c.detecting_regions(targets=["D0", "L0"])) == 2
    assert len(c.detecting_regions(targets=[stim.target_relative_detector_id(0), "D0"])) == 1


def test_detecting_regions_mzz():
    c = stim.Circuit("""
        TICK
        MZZ 0 1 1 2
        TICK
        M 2
        DETECTOR rec[-1]
    """)
    assert c.detecting_regions() == {
        stim.target_relative_detector_id(0): {
            0: stim.PauliString("__Z"),
            1: stim.PauliString("__Z"),
        },
    }


def test_insert():
    c = stim.Circuit()
    with pytest.raises(ValueError, match='type'):
        c.insert(0, object())
    with pytest.raises(ValueError, match='index <'):
        c.insert(1, stim.CircuitInstruction("H", [1]))
    with pytest.raises(ValueError, match='index <'):
        c.insert(-1, stim.CircuitInstruction("H", [1]))
    c.insert(0, stim.CircuitInstruction("H", [1]))
    assert c == stim.Circuit("""
        H 1
    """)

    with pytest.raises(ValueError, match='index <'):
        c.insert(2, stim.CircuitInstruction("S", [2]))
    with pytest.raises(ValueError, match='index <'):
        c.insert(-2, stim.CircuitInstruction("S", [2]))
    c.insert(0, stim.CircuitInstruction("S", [2, 3]))
    assert c == stim.Circuit("""
        S 2 3
        H 1
    """)

    c.insert(-1, stim.Circuit("H 5\nM 2"))
    assert c == stim.Circuit("""
        S 2 3
        H 5
        M 2
        H 1
    """)

    c.insert(2, stim.Circuit("""
        REPEAT 100 {
            M 3
        }
    """))
    assert c == stim.Circuit("""
        S 2 3
        H 5
        REPEAT 100 {
            M 3
        }
        M 2
        H 1
    """)

    c.insert(2, stim.Circuit("""
        REPEAT 100 {
            M 3
        }
    """)[0])
    assert c == stim.Circuit("""
        S 2 3
        H 5
        REPEAT 100 {
            M 3
        }
        REPEAT 100 {
            M 3
        }
        M 2
        H 1
    """)


def test_pop():
    with pytest.raises(IndexError, match='index'):
        stim.Circuit().pop()
    with pytest.raises(IndexError, match='index'):
        stim.Circuit().pop(-1)
    with pytest.raises(IndexError, match='index'):
        stim.Circuit().pop(0)
    c = stim.Circuit("H 0")
    with pytest.raises(IndexError, match='index'):
        c.pop(1)
    with pytest.raises(IndexError, match='index'):
        c.pop(-2)
    assert c.pop(0) == stim.CircuitInstruction("H", [0])
    c = stim.Circuit("H 0\n X 1")
    assert c.pop() == stim.CircuitInstruction("X", [1])
    assert c.pop() == stim.CircuitInstruction("H", [0])


def test_circuit_create_with_odd_cx():
    with pytest.raises(ValueError, match="0, 1, 2"):
        stim.Circuit("CX 0 1 2")


def test_to_tableau():
    assert stim.Circuit().to_tableau() == stim.Tableau(0)
    assert stim.Circuit("QUBIT_COORDS 0").to_tableau() == stim.Tableau(1)
    assert stim.Circuit("I 0").to_tableau() == stim.Tableau(1)
    assert stim.Circuit("H 0").to_tableau() == stim.Tableau.from_named_gate("H")
    assert stim.Circuit("CX 0 1").to_tableau() == stim.Tableau.from_named_gate("CX")
    assert stim.Circuit("SPP Z0").to_tableau() == stim.Tableau.from_named_gate("S")
    assert stim.Circuit("SPP X0").to_tableau() == stim.Tableau.from_named_gate("SQRT_X")
    assert stim.Circuit("SPP_DAG Y0*Y1").to_tableau() == stim.Tableau.from_named_gate("SQRT_YY_DAG")


def test_circuit_tags():
    c = stim.Circuit("""
        H[test] 0
    """)
    assert str(c) == "H[test] 0"
    assert c[0].tag == 'test'
    c.append(stim.CircuitInstruction('CX', [0, 1], tag='test2'))
    assert c[1].tag == 'test2'
    assert c == stim.Circuit("""
        H[test] 0
        CX[test2] 0 1
    """)
    assert c != stim.Circuit("""
        H 0
        CX 0 1
    """)


def test_circuit_add_tags():
    assert stim.Circuit("""
        H[test] 0
    """) + stim.Circuit("""
        CX[test2] 0 1
    """) == stim.Circuit("""
        H[test] 0
        CX[test2] 0 1
    """)


def test_circuit_eq_tags():
    assert stim.CircuitInstruction("TICK", tag="a") == stim.CircuitInstruction("TICK", tag="a")
    assert stim.CircuitInstruction("TICK", tag="a") != stim.CircuitInstruction("TICK", tag="b")
    assert stim.CircuitRepeatBlock(1, stim.Circuit(), tag="a") == stim.CircuitRepeatBlock(1, stim.Circuit(), tag="a")
    assert stim.CircuitRepeatBlock(1, stim.Circuit(), tag="a") != stim.CircuitRepeatBlock(1, stim.Circuit(), tag="b")
    assert stim.Circuit("""
        H[test] 0
    """) == stim.Circuit("""
        H[test] 0
    """)
    assert stim.Circuit("""
        H[test] 0
    """) != stim.Circuit("""
        H[test2] 0
    """)
    assert stim.Circuit("""
        H[test] 0
    """) != stim.Circuit("""
        H 0
    """)
    assert stim.Circuit("""
        H[] 0
    """) == stim.Circuit("""
        H 0
    """)


def test_circuit_get_item_tags():
    assert stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
        REPEAT[test3] 3 {
            M[test4](0.25) 4
        }
    """)[1] == stim.CircuitInstruction("CX[test2] 1 2")
    assert stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
        REPEAT[test3] 3 {
            M[test4](0.25) 4
        }
    """)[2] == stim.CircuitRepeatBlock(3, stim.Circuit("M[test4](0.25) 4"), tag="test3")
    assert stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
        REPEAT[test3] 3 {
            M[test4](0.25) 4
        }
    """)[1:3] == stim.Circuit("""
        CX[test2] 1 2
        REPEAT[test3] 3 {
            M[test4](0.25) 4
        }
    """)


def test_tags_iadd():
    c = stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
    """)
    c += stim.Circuit("""
        REPEAT[test3] 3 {
            M[test4](0.25) 4
        }
    """)
    assert c == stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
        REPEAT[test3] 3 {
            M[test4](0.25) 4
        }
    """)


def test_tags_imul():
    c = stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
    """)
    c *= 2
    assert c == stim.Circuit("""
        REPEAT 2 {
            H[test] 0
            CX[test2] 1 2
        }
    """)


def test_tags_mul():
    c = stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
    """)
    assert c * 2 == stim.Circuit("""
        REPEAT 2 {
            H[test] 0
            CX[test2] 1 2
        }
    """)


def test_tags_append():
    c = stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
    """)
    c.append(stim.CircuitRepeatBlock(3, stim.Circuit("""
        M[test4](0.25) 4
    """), tag="test3"))
    assert c == stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
        REPEAT[test3] 3 {
            M[test4](0.25) 4
        }
    """)


def test_tags_append_from_stim_program_text():
    c = stim.Circuit()
    c.append_from_stim_program_text("""
        H[test] 0
        CX[test2] 1 2
    """)
    assert c == stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
    """)


def test_tag_approx_equals():
    assert not stim.Circuit("H[test] 0").approx_equals(stim.Circuit("H[test2] 0"), atol=3)
    assert stim.Circuit("H[test] 0").approx_equals(stim.Circuit("H[test] 0"), atol=3)


def test_tag_clear():
    c = stim.Circuit("H[test] 0")
    c.clear()
    assert c == stim.Circuit()


def test_tag_compile_samplers():
    c = stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0
        M[test3](0.25) 0
        DETECTOR[test4](1, 2) rec[-1]
    """)
    s = c.compile_detector_sampler()
    assert 200 < np.sum(s.sample(shots=1000)) < 600
    s = c.compile_sampler()
    assert 200 < np.sum(s.sample(shots=1000)) < 600
    _ = c.compile_m2d_converter()


def test_tag_detector_error_model():
    dem = stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0
        M[test3](0.25) 0
        DETECTOR[test4](1, 2) rec[-1]
    """).detector_error_model()
    assert dem == stim.DetectorErrorModel("""
        error[test2](0.25) D0
        error[test3](0.25) D0
        detector[test4](1, 2) D0
    """)


def test_tag_copy():
    c = stim.Circuit("""
        H[test] 0
        CX[test2] 1 2
        REPEAT[test3] 3 {
            M[test4](0.25) 4
        }
    """).detector_error_model()
    cc = c.copy()
    assert cc is not c
    assert cc == c


def test_tag_count_determined_measurements():
    assert stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0
        M[test3](0.25) 0
        DETECTOR[test4](1, 2) rec[-1]
    """).count_determined_measurements() == 1


def test_tag_decomposed():
    assert stim.Circuit("""
        RX[test1] 0
        X_ERROR[test2](0.25) 0
        MPP[test3](0.25) X0*Z1
        DETECTOR[test4](1, 2) rec[-1]
        SPP[test5] Y0
    """).decomposed() == stim.Circuit("""
        R[test1] 0
        H[test1] 0
        X_ERROR[test2](0.25) 0
        H[test3] 0
        CX[test3] 1 0
        M[test3] 0
        CX[test3] 1 0
        H[test3] 0
        DETECTOR[test4](1, 2) rec[-1]
        H[test5] 0
        S[test5] 0
        H[test5] 0
        S[test5] 0 0 0
        H[test5] 0
        S[test5] 0
        H[test5] 0
        S[test5] 0 0
    """)


def test_tag_detecting_regions():
    assert stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0
        TICK
        M[test3](0.25) 0
        DETECTOR[test4](1, 2) rec[-1]
    """).detecting_regions() == {stim.DemTarget('D0'): {0: stim.PauliString("Z")}}


def test_tag_diagram():
    # TODO: include tags in diagrams
    assert str(stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0
        M[test3](0.25) 0
        DETECTOR[test4](1, 2) rec[-1]
    """).diagram()) == """
        q0: -R-X_ERROR(0.25)-M(0.25):rec[0]-DETECTOR(1,2):D0=rec[0]-
    """.strip()


def test_tag_flattened():
    assert stim.Circuit("""
        R[test1] 0
        REPEAT[test1.5] 2 {
            H[test2] 0
        }
    """).flattened() == stim.Circuit("""
        R[test1] 0
        H[test2] 0
        H[test2] 0
    """)


def test_tag_from_file():
    c = stim.Circuit.from_file(io.StringIO("""
        R[test1] 0
        REPEAT[test1.5] 2 {
            H[test2] 0
        }
    """))
    assert c == stim.Circuit("""
        R[test1] 0
        REPEAT[test1.5] 2 {
            H[test2] 0
        }
    """)
    s = io.StringIO()
    c.to_file(s)
    s.seek(0)
    assert s.read() == str(c) + '\n'


def test_tag_insert():
    c = stim.Circuit("""
        H[test1] 0
        S[test2] 0
    """)
    c.insert(1, stim.CircuitInstruction("CX[test3] 0 1"))
    assert c == stim.Circuit("""
        H[test1] 0
        CX[test3] 0 1
        S[test2] 0
    """)


def test_tag_fuse():
    c = stim.Circuit("""
        H[test1] 0
        H[test1] 0
        H[test2] 0
        H[test1] 0
    """)
    assert len(c) == 3
    assert c[0].tag == "test1"
    assert c[1].tag == "test2"
    assert c[2].tag == "test1"


def test_tag_inverse():
    assert stim.Circuit("""
        S[test1] 0
        CX[test2] 0 1
        SPP[test3] X0*Y1
        REPEAT[test4] 2 {
            H[test5] 0
        }
    """).inverse() == stim.Circuit("""
        REPEAT[test4] 2 {
            H[test5] 0
        }
        SPP_DAG[test3] Y1*X0
        CX[test2] 0 1
        S_DAG[test1] 0
    """)


def test_tag_time_reversed_for_flows():
    c, _ = stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0
        SQRT_X[test3] 0
        MY[test4] 0
        DETECTOR[test5] rec[-1]
    """).time_reversed_for_flows([])
    assert c == stim.Circuit("""
        RY[test4] 0
        SQRT_X_DAG[test3] 0
        X_ERROR[test2](0.25) 0
        M[test1] 0
        DETECTOR[test5] rec[-1]
    """)


def test_tag_with_inlined_feedback():
    assert stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0 1
        MR[test3] 0
        CX[test4] rec[-1] 1
        M[test5] 1
        DETECTOR[test6] rec[-1]
    """).with_inlined_feedback() == stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0 1
        MR[test3] 0
        M[test5] 1
        DETECTOR[test6] rec[-2] rec[-1]
    """)


def test_tag_without_noise():
    assert stim.Circuit("""
        R[test1] 0
        X_ERROR[test2](0.25) 0 1
        M[test3](0.25) 0
        DETECTOR[test4] rec[-1]
    """).without_noise() == stim.Circuit("""
        R[test1] 0
        M[test3] 0
        DETECTOR[test4] rec[-1]
    """)


def test_append_tag():
    c = stim.Circuit()
    c.append("H", [2, 3], tag="test")
    assert c == stim.Circuit("H[test] 2 3")

    with pytest.raises(ValueError, match="tag"):
        c.append(c[0], tag="newtag")

    with pytest.raises(ValueError, match="tag"):
        c.append(stim.CircuitRepeatBlock(10, stim.Circuit()), tag="newtag")

    assert c == stim.Circuit("H[test] 2 3")


def test_append_pauli_string():
    c = stim.Circuit()
    c.append("MPP", [
        stim.PauliString("X1*Y2*Z3"),
        stim.target_y(4),
        stim.PauliString("Z5"),
    ])
    assert c == stim.Circuit("""
        MPP X1*Y2*Z3 Y4 Z5
    """)
    c.append("MPP", stim.PauliString("X1*X2"))
    assert c == stim.Circuit("""
        MPP X1*Y2*Z3 Y4 Z5 X1*X2
    """)

    with pytest.raises(ValueError, match="empty stim.PauliString"):
        c.append("MPP", stim.PauliString(""))
    with pytest.raises(ValueError, match="empty stim.PauliString"):
        c.append("MPP", [stim.PauliString("")])
    with pytest.raises(ValueError, match="empty stim.PauliString"):
        c.append("MPP", [stim.PauliString("X1"), stim.PauliString("")])
    assert c == stim.Circuit("""
        MPP X1*Y2*Z3 Y4 Z5 X1*X2
    """)

    with pytest.raises(ValueError, match="Don't know how to target"):
        c.append("MPP", object())
    with pytest.raises(ValueError, match="Don't know how to target"):
        c.append("MPP", object())


def test_without_tags():
    circuit = stim.Circuit("""
        H[tag] 5
    """)
    assert circuit.without_tags() == stim.Circuit("""
        H 5
    """)


def test_reference_detector_and_observable_signs():
    det, obs = stim.Circuit("""
        X 1
        M 0 1
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        OBSERVABLE_INCLUDE(3) rec[-1] rec[-2]
    """).reference_detector_and_observable_signs()
    assert det.dtype == np.bool_
    assert obs.dtype == np.bool_
    np.testing.assert_array_equal(det, [True, False])
    np.testing.assert_array_equal(obs, [False, False, False, True])

    det, obs = stim.Circuit("""
        X 1
        M 0 1
        DETECTOR rec[-1]
        DETECTOR rec[-2]
        OBSERVABLE_INCLUDE(3) rec[-1] rec[-2]
    """).reference_detector_and_observable_signs(bit_packed=True)
    assert det.dtype == np.uint8
    assert obs.dtype == np.uint8
    np.testing.assert_array_equal(det, [0b01])
    np.testing.assert_array_equal(obs, [0b1000])

    circuit = stim.Circuit.generated("surface_code:rotated_memory_x", rounds=3, distance=3)
    det, obs = circuit.reference_detector_and_observable_signs(bit_packed=True)
    assert det.dtype == np.uint8
    assert obs.dtype == np.uint8
    assert not np.any(det)
    assert not np.any(obs)
    assert len(det) == (circuit.num_detectors + 7) // 8
    assert len(obs) == 1


def test_without_noise_removes_id_errors():
    assert stim.Circuit("""
        I_ERROR 0
        I_ERROR(0.25) 1
        II_ERROR 2 3
        II_ERROR(0.125) 3 4
        H 0
    """).without_noise() == stim.Circuit("""
        H 0
    """)
