import itertools
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterator, List, Tuple, Union

from dokusan.entities import Cell, Mark, Position, Sudoku


class NotFound(Exception):
    pass


@dataclass
class Result:
    positions: List[Position]
    values: List[int]
    changed_cells: List[Union[Cell, Mark]]


class LoneSingle:
    def __init__(self, sudoku: Sudoku):
        self.sudoku = sudoku

    def __iter__(self) -> Iterator[Result]:
        return (
            Result(
                positions=[cell.position],
                values=[cell.value],
                changed_cells=self._get_changed_cells(cell),
            )
            for cell in self._find()
        )

    def first(self) -> Result:
        try:
            return next(iter(self))
        except StopIteration:
            raise NotFound("No Lone Single found")

    def _find(self):
        for mark in self.sudoku.marks():
            if len(mark.candidates) == 1:
                yield Cell(position=mark.position, value=next(iter(mark.candidates)))

    def _get_changed_cells(self, single) -> List[Mark]:
        return [single] + [
            Mark(
                position=mark.position,
                candidates=mark.candidates - set([single.value]),
            )
            for mark in self.sudoku.intersection(single)
            if isinstance(mark, Mark) and mark.candidates & set([single.value])
        ]


class HiddenSingle:
    def __init__(self, sudoku: Sudoku):
        self.sudoku = sudoku

    def __iter__(self) -> Iterator[Result]:
        return (
            Result(
                positions=[cell.position],
                values=[cell.value],
                changed_cells=self._get_changed_cells(cell),
            )
            for cell in self._find()
        )

    def first(self) -> Result:
        try:
            return next(iter(self))
        except StopIteration:
            raise NotFound("No Hidden Single found")

    def _find(self):
        for house in self.sudoku.rows() + self.sudoku.columns() + self.sudoku.squares():
            groups: Dict[int, List[Mark]] = {}
            for mark in house:
                if isinstance(mark, Mark):
                    for candidate in mark.candidates:
                        groups.setdefault(candidate, []).append(mark)

            for candidate, marks in groups.items():
                if len(marks) == 1:
                    yield Cell(position=marks[0].position, value=candidate)

    def _get_changed_cells(self, single) -> List[Mark]:
        return [single] + [
            Mark(
                position=mark.position,
                candidates=mark.candidates - set([single.value]),
            )
            for mark in self.sudoku.intersection(single)
            if isinstance(mark, Mark) and mark.candidates & set([single.value])
        ]


class NakedPair:
    def __init__(self, sudoku: Sudoku):
        self.sudoku = sudoku

    def __iter__(self) -> Iterator[Result]:
        return (
            Result(
                positions=[cell.position for cell in pair],
                values=pair[0].candidates,
                changed_cells=changed_cells,
            )
            for pair in self._find()
            if (changed_cells := self._get_changed_cells(pair))
        )

    def first(self) -> Result:
        try:
            return next(iter(self))
        except StopIteration:
            raise NotFound("No Naked Pair found")

    def _find(self):
        for house in self.sudoku.rows() + self.sudoku.columns() + self.sudoku.squares():
            groups: Dict[Tuple[int, ...], List[Mark]] = {}
            for mark in house:
                if isinstance(mark, Mark):
                    groups.setdefault(tuple(mark.candidates), []).append(mark)

            for candidates, marks in groups.items():
                if len(candidates) == 2 and len(marks) == 2:
                    yield marks

    def _get_changed_cells(self, pair) -> List[Mark]:
        return [
            Mark(
                position=mark.position, candidates=mark.candidates - pair[0].candidates,
            )
            for mark in self.sudoku.intersection(*pair)
            if isinstance(mark, Mark) and mark.candidates & pair[0].candidates
        ]


class NakedTriplet:
    def __init__(self, sudoku: Sudoku):
        self.sudoku = sudoku

    def __iter__(self) -> Iterator[Result]:
        return (
            Result(
                positions=[cell.position for cell in triplet],
                values=list(set.union(*[t.candidates for t in triplet])),
                changed_cells=changed_cells,
            )
            for triplet in self._find()
            if (changed_cells := self._get_changed_cells(triplet))
        )

    def first(self) -> Result:
        try:
            return next(iter(self))
        except StopIteration:
            raise NotFound("No Naked Triplet found")

    def _find(self):
        for house in self.sudoku.rows() + self.sudoku.columns() + self.sudoku.squares():
            marks = [mark for mark in house if isinstance(mark, Mark)]
            counter = Counter(tuple(mark.candidates) for mark in marks)

            for pair, count in counter.items():
                if 2 <= count < 4:
                    triplet = [m for m in marks if len(m.candidates.union(pair)) < 4]
                    if len(triplet) == 3:
                        yield triplet

    def _get_changed_cells(self, triplet) -> List[Mark]:
        candidates = set.union(*[t.candidates for t in triplet])
        return [
            Mark(position=mark.position, candidates=mark.candidates - candidates)
            for mark in self.sudoku.intersection(*triplet)
            if isinstance(mark, Mark) and mark.candidates & candidates
        ]


class Omission:
    def __init__(self, sudoku: Sudoku):
        self.sudoku = sudoku

    def __iter__(self) -> Iterator[Result]:
        return (
            Result(
                positions=[cell.position for cell in omission[1:]],
                values=[omission[0]],
                changed_cells=changed_cells,
            )
            for omission in self._find()
            if (changed_cells := self._get_changed_cells(omission))
        )

    def first(self) -> Result:
        try:
            return next(iter(self))
        except StopIteration:
            raise NotFound("No Omission found")

    def _find(self):
        for house in self.sudoku.rows() + self.sudoku.columns() + self.sudoku.squares():
            groups: Dict[int, List[Mark]] = {}
            for mark in house:
                if isinstance(mark, Mark):
                    for candidate in mark.candidates:
                        groups.setdefault(candidate, []).append(mark)

            for candidate, marks in groups.items():
                if len(marks) == 2:
                    yield [candidate, *marks]

    def _get_changed_cells(self, omission):
        eliminated = set([omission[0]])
        return [
            Mark(position=mark.position, candidates=mark.candidates - eliminated)
            for mark in self.sudoku.intersection(*omission[1:])
            if isinstance(mark, Mark) and mark.candidates & eliminated
        ]


class XYWing:
    def __init__(self, sudoku: Sudoku):
        self.sudoku = sudoku

    def __iter__(self) -> Iterator[Result]:
        return (
            Result(
                positions=[cell.position for cell in xy_wing],
                values=[
                    next(iter(cell_a.candidates & cell_b.candidates))
                    for cell_a, cell_b in itertools.combinations(xy_wing, r=2)
                    if not self.sudoku.is_intersects(cell_a, cell_b)
                ],
                changed_cells=changed_cells,
            )
            for xy_wing in self._find()
            if (changed_cells := self._get_changed_cells(xy_wing))
        )

    def first(self) -> Result:
        try:
            return next(iter(self))
        except StopIteration:
            raise NotFound("No XYWing found")

    def _find(self):
        marks = [mark for mark in self.sudoku.marks() if len(mark.candidates) == 2]
        for wing in itertools.combinations(marks, 3):
            if self._is_xy_wing(wing):
                yield wing

    def _is_xy_wing(self, marks) -> bool:
        combinations = tuple(itertools.combinations(marks, 2))
        if sum(self.sudoku.is_intersects(a, b) for a, b in combinations) != 2:
            return False
        if any(len(a.candidates & b.candidates) != 1 for a, b in combinations):
            return False
        if len(set.union(*[m.candidates for m in marks])) != 3:
            return False
        return True

    def _get_changed_cells(self, xy_wing):
        for cell_a, cell_b in itertools.combinations(xy_wing, 2):
            if not self.sudoku.is_intersects(cell_a, cell_b):
                eliminated = cell_a.candidates & cell_b.candidates
                return [
                    Mark(position=m.position, candidates=m.candidates - eliminated)
                    for m in self.sudoku.intersection(cell_a, cell_b)
                    if isinstance(m, Mark) and m.candidates & eliminated
                ]


class UniqueRectangle:
    def __init__(self, sudoku: Sudoku):
        self.sudoku = sudoku

    def __iter__(self) -> Iterator[Result]:
        return (
            Result(
                positions=[edge.position for edge in rectangle],
                values=sorted(rectangle[0].candidates & rectangle[1].candidates),
                changed_cells=changed_cells,
            )
            for rectangle in self._find()
            if (changed_cells := self._get_changed_cells(rectangle))
        )

    def first(self) -> Result:
        try:
            return next(iter(self))
        except StopIteration:
            raise NotFound("No Unique Rectangle found")

    def _find(self):
        marks = [mark for mark in self.sudoku.marks() if len(mark.candidates) == 2]
        for edges in itertools.combinations(marks, r=3):
            if self._is_edges(edges):
                rows = {edge.position.row for edge in edges}
                cols = {edge.position.column for edge in edges}
                rectangle = [self.sudoku[pos] for pos in itertools.product(rows, cols)]
                if self._is_rect(rectangle):
                    yield rectangle

    def _is_edges(self, marks) -> bool:
        if len(set.intersection(*[m.candidates for m in marks])) != 2:
            return False
        combinations = tuple(itertools.combinations(marks, 2))
        if sum(a.position.square == b.position.square for a, b in combinations) != 1:
            return False
        return True

    def _is_rect(self, marks) -> bool:
        if any(isinstance(cell, Cell) for cell in marks):
            return False
        if len(set.intersection(*[m.candidates for m in marks])) != 2:
            return False
        return True

    def _get_changed_cells(self, rectangle):
        for edge_a in rectangle:
            for edge_b in rectangle:
                if diff := (edge_a.candidates - edge_b.candidates):
                    return [Mark(position=edge_a.position, candidates=diff)]
