// The group read (his yes, Fri 23/10/2026): the industry the fundamentals sheet
// names and "N of M in the group fired tonight, K in the last 10 days". Every
// number arrives resolved from the scan; this module only labels it (EC-28):
// no sort, no gate, no judgment. Measured first on the archive: the counts pay
// nothing in the tail; they are shown because the picture was missing.
import { EMPTY, finiteOrNull } from '../formatting/format.js';

const SHOWN_ONLY = 'Shown only: the group never changes the grade, the tier or the order.';

// A payload written before the group read existed carries no `group`; a fired
// name whose sheet names no industry carries null.
export const hasGroupRead = (data) => typeof data?.group?.industry === 'string' && data.group.industry !== '';

const counts = (group) => ({
  tonight: finiteOrNull(group?.fired_tonight),
  window: finiteOrNull(group?.fired_10d),
  members: finiteOrNull(group?.members),
});

// "7 of 9 fired tonight, 8 in the last 10 days"
export const groupSentence = (group) => {
  const { tonight, window, members } = counts(group);
  if (tonight == null || members == null) return EMPTY;
  const head = `${tonight} of ${members} fired tonight`;
  return window == null ? head : `${head}, ${window} in the last 10 days`;
};

// The card's compact text: "7 of 9".
export const groupCardText = (group) => {
  const { tonight, members } = counts(group);
  return tonight == null || members == null ? EMPTY : `${tonight} of ${members}`;
};

export const groupTitle = (group) =>
  `${group?.industry || 'Group'}: ${groupSentence(group)} (the group is the names of this industry in the scanned universe, as far as the scan knows them). ${SHOWN_ONLY}`;

// The detail grid's two cells.
export const groupCells = (data) => {
  const group = data?.group;
  const { tonight, window, members } = counts(group);
  const fired = tonight == null || members == null
    ? EMPTY
    : `${tonight} of ${members} tonight${window == null ? '' : ` · ${window} in 10d`}`;
  return [
    { k: 'Group', v: group?.industry || EMPTY, title: `Industry, the vendor's word on the fundamentals sheet. ${SHOWN_ONLY}` },
    { k: 'Group fired', v: fired, title: groupTitle(group) },
  ];
};
