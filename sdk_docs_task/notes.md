# Week 5 Open Coding

## Random Sample

- Seed: 20260905
- Population: 42
- Sample size: 20

## Open-Coding Notes

### 1. tr_0fc171f43407

**Question:** 14. What is the performance review process?

**Observation:** The answer describes monthly evaluations after six months, two evaluations for new employees, and confirmation after positive feedback, all of which appear in the retrieved performance-review chunks.

### 2. tr_146f1666a17c

**Question:** What about 24

**Observation:** The answer identifies section 24 as “CONTACT DETAILS,” matching the section heading in the first two retrieved chunks.

### 3. tr_190d9cf99f22

**Question:** What is HR policy ?

**Observation:** The answer combines orientation, account setup, payroll, equal opportunity, exit, and leave topics from the three retrieved chunks into a broad description of HR policy.

### 4. tr_20608975fe4f

**Question:** When was the recent modification ddate ?

**Observation:** The answer gives June 2025 as the most recent modification date, which is shown as Revision 11 in retrieved chunk_98.

### 5. tr_276aa5f3ef2c

**Question:** Give me a contact detials?

**Observation:** The answer says the document lacks the information even though the top retrieved chunk contains the “24. CONTACT DETAILS” heading.

### 6. tr_2c4ad90dfe82

**Question:** What about 9,10,11

**Observation:** The answer lists the leave subsections under section 9 and names sections 10 and 11, following the table-of-contents material in the retrieved chunks.

### 7. tr_6646b33397c9

**Question:** 21. Who can approve employee leave?

**Observation:** The answer says a Team Leader or Manager can approve leave, consistent with the retrieved chunk requiring TL/Manager approval before an ERP leave request.

### 8. tr_746f891ceca5

**Question:** 15. What is the salary revision policy?

**Observation:** The answer says it does not know the salary revision policy while the retrieved chunks contain a table of contents, handbook revisions, and text about arrears and pro-rata processing.

### 9. tr_7514244d35bf

**Question:** 25. How are policy changes communicated to employees?

**Observation:** The answer says revisions are communicated when they come into effect, matching the wording in retrieved chunks_8 and _9.

### 10. tr_78754e76adc1

**Question:** 17. What is the remote work policy?

**Observation:** The answer says the document lacks remote-work details even though one retrieved chunk contains work-from-home instructions about reporting incidents and maintaining a backup plan.

### 11. tr_7e34fe528b4e

**Question:** What is electronic equipment usage policy ?

**Observation:** The answer says electronic equipment includes computers, telephones, voicemail, hardware, and related devices and should be used economically and responsibly, reflecting chunk_68.

### 12. tr_7e4897d361e9

**Question:** 16. What is the overtime policy?

**Observation:** The answer says no overtime-policy description is available even though the top retrieved chunk states that refusal to work overtime due to work exigencies is listed among misconduct items.

### 13. tr_8b9c3dd04f50

**Question:** 12. What is the maternity leave policy?

**Observation:** The answer gives the 80-day eligibility condition, 26-week maximum, medical-certificate requirement, and two-live-birth limit stated in retrieved chunk_53.

### 14. tr_b93b7072265b

**Question:** 7. What is the late-arrival policy?

**Observation:** The answer says employees must arrive on time and that repeated or unjustified lateness may lead to disciplinary action, while the retrieved chunks define tardiness and require employees to report and return from breaks on time.

### 15. tr_bd6760f39065

**Question:** 5. What are the working hours?

**Observation:** The answer gives the technical and non-technical shifts, the 9.5-hour daily requirement, and the one-hour break stated in retrieved chunk_11.

### 16. tr_ce519229a818

**Question:** No ,CEO is Ramesh�?_Vayavuru.  Manohar�?_Vayyavuru is a managing director

**Observation:** The answer agrees with the correction and assigns Ramesh Vayavuru to Chief Executive Officer and Manohar Vayyavuru to Managing Director, as separately labeled in chunk_99.

### 17. tr_dee920af8473

**Question:** 9. What is the notice period?

**Observation:** The answer gives a three-month resignation notice period, which is stated in retrieved chunks_37 and _38.

### 18. tr_e06a2639af0f

**Question:** Who is the CEO of the comapny

**Observation:** The answer presents Ramesh Vayavuru and Manohar Vayyavuru as a combined CEO name, while the top retrieved chunk separately labels Ramesh as Chief Executive Officer and Manohar as Managing Director.

### 19. tr_e9c8155fb64f

**Question:** 22. What happens if an employee violates company policy? \\

**Observation:** The answer lists reprimand, suspension, termination, and benefit deduction or suspension as possible consequences, matching the disciplinary-action text in chunk_97.

### 20. tr_ff5f5b4df2e7

**Question:** Give me contact detials \\

**Observation:** The answer says the document contains no contact details even though the retrieved material includes the “24. CONTACT DETAILS” heading.

## Falsifiable Prediction

- **Date:** 2026-09-05
- **Failure mode:** Answer declares information unavailable despite related retrieved material.
- **Baseline:** 4/20 traces = 20%.
- **Proposed change:** Change the RAG answer-generation step to more explicitly use retrieved evidence when answering.
- **Prediction:** On a new seeded 20-trace evaluation sample, this failure mode will decrease from 20% (4/20) to <=10% (2/20 or fewer).
- **Evaluation sample size:** 20 traces.

Git commit: not created by request; prediction recorded locally.

## Why a Public Benchmark Would Not Surface the Top 3 Modes

Generic public benchmarks often use clean, well-formed questions, so they may not exercise naturally typed or ambiguous HR-policy requests such as "What about 24" and the broad HR-policy query seen in this sample.
They may score broad answer correctness without checking whether an answer that says information is unavailable ignored related retrieved evidence, as in the contact-details and remote-work traces.
They also may not include organization-specific entity and role distinctions, such as the traces that separately label Ramesh Vayavuru as CEO and Manohar Vayyavuru as Managing Director.
