"""The roles a box can hold in a two-eyes read — the ONE tuple.

A module of its own, with no imports, for one reason: the archive writer the
OLD reader's nightly scan uses needs these words (the LPS column's closed set),
and taking them from `engine_alpha.two_eyes.record` would import the whole
new-reader package — every stage the rewrite adds — into the old reader's
nightly path. A broken new-reader module could then stop the scan with the
switch off, which is the one thing the door was built to prevent. Here, the
record and the archive both take the same tuple, and neither drags the other
along.

The parent is the setup's own box, a mini lives inside the parent's life, and
earlier is a pair the walk tried and left behind.
"""

ROLE_PARENT = "parent"
ROLE_MINI = "mini"
ROLE_EARLIER = "earlier"
ROLES = (ROLE_PARENT, ROLE_MINI, ROLE_EARLIER)
