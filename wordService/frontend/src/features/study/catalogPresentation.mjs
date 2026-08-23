// Keep the API's book summary and section metadata immutable. The study wall
// changes its visible scope often, so its counters must be derived from those
// source values instead of written back into them.
export function deriveCatalogPresentation({
  bookSummary,
  sourceUnits,
  allEntries,
  selectedBook,
  selectedUnit,
  cards,
  markStatusOf,
  isReviewDue,
}) {
  const bookEntries = allEntries.filter((entry) => entry.book_code === selectedBook);
  const scopedEntries = selectedUnit === null
    ? bookEntries
    : bookEntries.filter((entry) => entry.unit.number === selectedUnit);

  const countsFor = (entries) => {
    const marks = entries.map((entry) => cards[entry.item_uuid]);
    const known = marks.filter((mark) => markStatusOf(mark) === "known").length;
    const flagged = marks.filter((mark) => markStatusOf(mark) === "flagged").length;
    const review = marks.filter((mark) => isReviewDue(mark?.due_at)).length;
    return {
      known,
      flagged,
      review,
      unmarked: marks.filter((mark) => markStatusOf(mark) === "unmarked").length,
    };
  };

  return {
    summary: {
      ...bookSummary,
      entries: scopedEntries.length,
      units: selectedUnit === null ? bookSummary.units : 1,
      ...countsFor(scopedEntries),
    },
    units: sourceUnits.map((unit) => ({
      ...unit,
      ...countsFor(bookEntries.filter((entry) => entry.unit.number === unit.number)),
    })),
  };
}
