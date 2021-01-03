#include <iostream>
#include <map>
#include "pauli_string.h"
#include "vector_sim.h"

VectorSim::VectorSim(size_t num_qubits) {
    state.resize(1 << num_qubits, 0.0f);
    state[0] = 1;
}

std::vector<std::complex<float>> mat_vec_mul(const std::vector<std::vector<std::complex<float>>> &matrix,
                                             const std::vector<std::complex<float>> &vec) {
    std::vector<std::complex<float>> result;
    for (size_t row = 0; row < vec.size(); row++) {
        std::complex<float> v = 0;
        for (size_t col = 0; col < vec.size(); col++) {
            v += matrix[row][col] * vec[col];
        }
        result.push_back(v);
    }
    return result;
}

void VectorSim::apply(const std::vector<std::vector<std::complex<float>>> &matrix, const std::vector<size_t> &qubits) {
    size_t n = 1 << qubits.size();
    assert(matrix.size() == n);
    std::vector<size_t> masks;
    for (size_t k = 0; k < n; k++) {
        size_t m = 0;
        for (size_t q = 0; q < qubits.size(); q++) {
            if (k & (1 << q)) {
                m |= 1 << qubits[q];
            }
        }
        masks.push_back(m);
    }
    assert(masks.back() < state.size());
    for (size_t base = 0; base < state.size(); base++) {
        if (base & masks.back()) {
            continue;
        }
        std::vector<std::complex<float>> in;
        in.reserve(masks.size());
        for (auto m : masks) {
            in.push_back(state[base | m]);
        }
        auto out = mat_vec_mul(matrix, in);
        for (size_t k = 0; k < masks.size(); k++) {
            state[base | masks[k]] = out[k];
        }
    }
}

void VectorSim::apply(const std::string &gate, size_t qubit) {
    apply(GATE_UNITARIES.at(gate), {qubit});
}

void VectorSim::apply(const std::string &gate, size_t qubit1, size_t qubit2) {
    apply(GATE_UNITARIES.at(gate), {qubit1, qubit2});
}

void VectorSim::apply(const PauliString &gate, size_t qubit_offset) {
    if (gate._sign) {
        for (auto &e : state) {
            e *= -1;
        }
    }
    for (size_t k = 0; k < gate.size; k++) {
        bool x = gate.get_x_bit(k);
        bool y = gate.get_y_bit(k);
        size_t q = qubit_offset + k;
        if (x && y) {
            apply("Z", q);
        } else if (x) {
            apply("X", q);
        } else if (y) {
            apply("Y", q);
        }
    }
}

constexpr std::complex<float> i = std::complex<float>(0, 1);
constexpr std::complex<float> s = 0.7071067811865475244f;
const std::map<std::string, const std::vector<std::vector<std::complex<float>>>> GATE_UNITARIES {
    {"I", {{1, 0}, {0, 1}}},
    // Pauli gates.
    {"X", {{0, 1}, {1, 0}}},
    {"Y", {{0, -i}, {i, 0}}},
    {"Z", {{1, 0}, {0, -1}}},
    // Axis exchange gates.
    {"H", {{s, s}, {s, -s}}},
    {"H_XY", {{0, s - i*s}, {s + i*s, 0}}},
    {"H_XZ", {{s, s}, {s, -s}}},
    {"H_YZ", {{s, -i*s}, {i*s, -s}}},
    // 90 degree rotation gates.
    {"SQRT_X", {{0.5f + 0.5f*i, 0.5f - 0.5f*i}, {0.5f - 0.5f*i, 0.5f + 0.5f*i}}},
    {"SQRT_X_DAG", {{0.5f - 0.5f*i, 0.5f + 0.5f*i}, {0.5f + 0.5f*i, 0.5f - 0.5f*i}}},
    {"SQRT_Y", {{0.5f + 0.5f*i, -0.5f - 0.5f*i}, {0.5f + 0.5f*i, 0.5f + 0.5f*i}}},
    {"SQRT_Y_DAG", {{0.5f - 0.5f*i, 0.5f - 0.5f*i}, {-0.5f + 0.5f*i, 0.5f - 0.5f*i}}},
    {"SQRT_Z", {{1, 0}, {0, i}}},
    {"SQRT_Z_DAG", {{1, 0}, {0, -i}}},
    {"S", {{1, 0}, {0, i}}},
    {"S_DAG", {{1, 0}, {0, -i}}},
    // Two qubit gates.
    {"CNOT", {{1, 0, 0, 0}, {0, 0, 0, 1}, {0, 0, 1, 0}, {0, 1, 0, 0}}},
    {"CZ", {{1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, 1, 0}, {0, 0, 0, -1}}},
    {"SWAP", {{1, 0, 0, 0}, {0, 0, 1, 0}, {0, 1, 0, 0}, {0, 0, 0, 1}}},
};