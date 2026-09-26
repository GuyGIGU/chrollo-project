export const explainTip = ({ what, why, use }) => (
  [
    `What it is: ${what}`,
    `Why it matters: ${why}`,
    `How to use it: ${use}`,
  ].join(' ')
);
