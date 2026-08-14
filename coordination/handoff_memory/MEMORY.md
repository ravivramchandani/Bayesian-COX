# Working memory

Durable context about how work proceeds on this project, beyond what the
other coordination files record.

---

## Execution is autonomous

Implementation does not wait on approvals. Ordinary engineering choices are
resolved and recorded, not escalated. Work stops only for a genuinely missing
file or an irreversible external action. See `PROTOCOL.md`.

## Administrative matters are owner-managed

Approvals, access, credentials, ethics, permissions and supervisor sign-off
belong to Ali. They are recorded once in `OPEN_QUESTIONS.md` under "Owner
track" and never restated or used as a gate. Each names the single
deliverable it blocks; everything around it gets built.

## Writing style

Repository content stays clear, simple and professional. No decorative
headers, no comments restating code, no process narration, no status chatter.
Write the minimum a competent reader needs.

## Environment

Conda environment `bayes-cox`. PyMC chains run sequentially because the
parallel sampler is unreliable on this machine.

## Trust nothing that was not verified

The project previously carried a full set of results, figures and reports
that were entirely produced from synthetic data, with convergence diagnostics
that returned fixed passing values. Every claim now has a test behind it. When
adding a result, add the check that would catch it being wrong.
