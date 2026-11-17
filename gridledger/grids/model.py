from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class Cell:
    grid_id: int
    id: tuple[int, int]
    bounds: tuple[Fraction, Fraction, Fraction, Fraction]

    @property
    def area(self):
        x0, y0, x1, y1 = self.bounds
        return (x1 - x0) * (y1 - y0)

@dataclass(frozen=True)
class FaceUse:
    grid_id: int
    cell_id: tuple[int, int]
    side: str
    face_id: tuple[str, int, int]
    sign: int

@dataclass(frozen=True)
class Face:
    grid_id: int
    id: tuple[str, int, int]
    endpoints: tuple[tuple[Fraction, Fraction], tuple[Fraction, Fraction]]
    uses: tuple[FaceUse, ...]

@dataclass(frozen=True)
class GridRevision:
    id: int
    name: str
    shape: tuple[int, int]
    origin: tuple[Fraction, Fraction]
    spacing: tuple[Fraction, Fraction]
    cells: tuple[Cell, ...]
    faces: tuple[Face, ...]

    def cell(self, cell_id):
        for cell in self.cells:
            if cell.id == cell_id:
                return cell
        raise KeyError((self.id, cell_id))

    def face(self, face_id):
        for face in self.faces:
            if face.id == face_id:
                return face
        raise KeyError((self.id, face_id))
