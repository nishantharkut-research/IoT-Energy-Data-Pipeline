# Desktop layout corrections

Scope: desktop dashboard only, following the user's explicit instruction. Mobile-only changes explored during investigation were discarded.

Reproduced defects:
- The watermark connector left only 0.125 px between adjacent text at desktop width.
- Metric values differed vertically by about 20 px when their titles wrapped.
- A forced 500 px minimum made simple count tables scroll inside smaller desktop panels.
- Long 1M conservation equations wrapped their final unit onto a separate line at 1024 px.

Corrections: remove the redundant watermark connector, reserve two lines for metric titles, allow native table sizing, and give the equations full width on smaller desktop windows. Remove course/institution branding, shorten the overview heading, and disable spellchecking in identifier selectors.

Verification: visually inspect desktop captures, selected 1M results and open dialogs; run 74 rendered desktop layout/state cases across eight viewport sizes. Add this check to CI. Regenerate the report captures and PDF, preserve original result bytes, and publish the update.
