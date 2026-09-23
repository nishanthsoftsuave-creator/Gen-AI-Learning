# Week 5 Failure Taxonomy

| Failure Mode | Count | Percentage | Severity | Example Trace |
| ------------ | ----: | ---------: | -------- | ------------- |
| Answer declares information unavailable despite related retrieved material | 4 | 20% | Ships broken code | tr_78754e76adc1 |
| Broad answer to an ambiguous request | 2 | 10% | Annoys reader | tr_190d9cf99f22 |
| Separate people presented as one role-holder | 1 | 5% | Ships broken code | tr_e06a2639af0f |
| Unable-to-answer response with partially related retrieved material | 1 | 5% | Annoys reader | tr_746f891ceca5 |

## Failure-Mode Evidence

### Answer declares information unavailable despite related retrieved material

These answers decline to provide information while their retrieved material includes a related section heading or substantive policy-related text. For example, tr_78754e76adc1 says remote-work details are absent while a retrieved chunk contains work-from-home instructions.

### Broad answer to an ambiguous request

These answers combine several retrieved topics into a broad answer rather than staying tightly scoped to one directly stated policy. In tr_190d9cf99f22, the response combines orientation, account setup, payroll, equal opportunity, exit, and leave topics into a general HR-policy description.

### Separate people presented as one role-holder

The answer in this cluster joins two separately labeled people into one CEO name. In tr_e06a2639af0f, the retrieved chunk labels Ramesh Vayavuru as Chief Executive Officer and Manohar Vayyavuru as Managing Director.

### Unable-to-answer response with partially related retrieved material

The answer says it does not know the requested policy, while the retrieved material contains related but not clearly sufficient text. In tr_746f891ceca5, the chunks include a table of contents, handbook revisions, and arrears/pro-rata text rather than a direct salary-revision policy statement.

## Sample

- Seed: 20260905
- Population: 42
- Sample size: 20

## Trace Assignment

| Trace ID | Assignment |
| -------- | ---------- |
| tr_0fc171f43407 | Successful/acceptable — no failure evidence observed |
| tr_146f1666a17c | Successful/acceptable — no failure evidence observed |
| tr_190d9cf99f22 | Broad answer to an ambiguous request |
| tr_20608975fe4f | Successful/acceptable — no failure evidence observed |
| tr_276aa5f3ef2c | Answer declares information unavailable despite related retrieved material |
| tr_2c4ad90dfe82 | Broad answer to an ambiguous request |
| tr_6646b33397c9 | Successful/acceptable — no failure evidence observed |
| tr_746f891ceca5 | Unable-to-answer response with partially related retrieved material |
| tr_7514244d35bf | Successful/acceptable — no failure evidence observed |
| tr_78754e76adc1 | Answer declares information unavailable despite related retrieved material |
| tr_7e34fe528b4e | Successful/acceptable — no failure evidence observed |
| tr_7e4897d361e9 | Answer declares information unavailable despite related retrieved material |
| tr_8b9c3dd04f50 | Successful/acceptable — no failure evidence observed |
| tr_b93b7072265b | Successful/acceptable — no failure evidence observed |
| tr_bd6760f39065 | Successful/acceptable — no failure evidence observed |
| tr_ce519229a818 | Successful/acceptable — no failure evidence observed |
| tr_dee920af8473 | Successful/acceptable — no failure evidence observed |
| tr_e06a2639af0f | Separate people presented as one role-holder |
| tr_e9c8155fb64f | Successful/acceptable — no failure evidence observed |
| tr_ff5f5b4df2e7 | Answer declares information unavailable despite related retrieved material |

## Verification

- Actual failure behavior: 8/20 traces (40%)
- Successful/acceptable behavior: 12/20 traces (60%)
- Failure modes: 4
- Traces assigned: 20
- Duplicate trace assignments: 0
- Omitted trace assignments: 0
- Failure-mode percentages are calculated against all 20 traces and total 40%; the remaining 60% is the successful/acceptable portion of the sample, not a failure mode.
- Source/application code changed: no
