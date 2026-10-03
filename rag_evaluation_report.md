# AEGIS — End-to-End RAG Evaluation Report

Generated: `2026-10-02 09:42:59 UTC`

## Benchmark Scope

- Benchmark: `golden_questions.json`
- Total questions: **20**
- Questions with sufficient evidence: **13**
- Questions requiring refusal: **7**

## Metrics

- Status accuracy: **100.00%**
- Source retrieval accuracy: **100.00%**
- Answer relevance: **84.62%**
- Groundedness: **84.62%**
- Citation Precision: **88.46%**
- Citation Completeness: **96.70%**
- Safe refusal accuracy: **100.00%**

## Metric Definitions

- **Status accuracy:** Knowledge Guard returns the expected `SUFFICIENT` or `INSUFFICIENT` status.
- **Source retrieval accuracy:** expected source appears in retrieved evidence for answerable questions.
- **Answer relevance:** generated answer contains the expected answer from the toy benchmark.
- **Groundedness:** strict Citation Validator accepts every generated factual claim.
- **Citation Precision:** fraction of claim-to-citation pairs semantically supported by evidence.
- **Citation Completeness:** fraction of factual claims carrying at least one citation.
- **Safe refusal accuracy:** questions without sufficient knowledge are refused before LLM answer generation.

## Failure Analysis

### q003

**Question:** What changed between the old P-481 manual and the current service bulletin?

**Failure reasons:**
- Generated answer does not contain the expected benchmark answer.
- Citation validation failed: answer is not fully grounded.

**Generated answer:**

```text
The pressure sensor for Pump P-481 changed from E17 [C2] to E21 [C1].

- [C2] refers to the superseded service manual v2.1, which specifies pressure sensor E17.
- [C1] refers to the current service bulletin SB-104 v1.0, which specifies pressure sensor E21.

This statement concisely addresses the change in the pressure sensor model for Pump P-481 based on the provided evidence, with each citation corresponding to the relevant source.

\boxed{\text{The pressure sensor for Pump P-481 changed from E17 [C2] to E21 [C1]}}
```

**Citation Precision:** 0.5

**Citation Completeness:** 0.571

### q008

**Question:** Does Service Bulletin SB-104 supersede the P-481 Service Manual?

**Failure reasons:**
- Generated answer does not contain the expected benchmark answer.

**Generated answer:**

```text
Yes, Service Bulletin SB-104 supersedes the Pump P-481 Service Manual [C1].
```

**Citation Precision:** 1.0

**Citation Completeness:** 1.0

### q013

**Question:** In which section of the old P-481 manual is the pressure sensor specified?

**Failure reasons:**
- Citation validation failed: answer is not fully grounded.

**Generated answer:**

```text
The pressure sensor is specified in the "Pressure Sensor" section of the old P-481 manual [C2].
```

**Citation Precision:** 0.0

**Citation Completeness:** 1.0

## Per-Question Results

| ID | Expected status | Actual status | Status | Source | Relevance | Grounded | Citation Precision | Citation Completeness |
|---|---|---|---|---|---|---|---:|---:|
| q001 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q002 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q003 | SUFFICIENT | SUFFICIENT | True | True | False | False | 0.5 | 0.571 |
| q004 | INSUFFICIENT | INSUFFICIENT | True | True | True | True | N/A | N/A |
| q005 | INSUFFICIENT | INSUFFICIENT | True | True | True | True | N/A | N/A |
| q006 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q007 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q008 | SUFFICIENT | SUFFICIENT | True | True | False | True | 1.0 | 1.0 |
| q009 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q010 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q011 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q012 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q013 | SUFFICIENT | SUFFICIENT | True | True | True | False | 0.0 | 1.0 |
| q014 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q015 | SUFFICIENT | SUFFICIENT | True | True | True | True | 1.0 | 1.0 |
| q016 | INSUFFICIENT | INSUFFICIENT | True | True | True | True | N/A | N/A |
| q017 | INSUFFICIENT | INSUFFICIENT | True | True | True | True | N/A | N/A |
| q018 | INSUFFICIENT | INSUFFICIENT | True | True | True | True | N/A | N/A |
| q019 | INSUFFICIENT | INSUFFICIENT | True | True | True | True | N/A | N/A |
| q020 | INSUFFICIENT | INSUFFICIENT | True | True | True | True | N/A | N/A |

## Current Benchmark Limitation

This is a local toy benchmark over two documents. It validates the Aegis pipeline mechanics, but it does not yet represent production diversity of document types, assets, permissions, or multi-hop Graph RAG questions.
