#!/usr/bin/env python3
"""
Convert tiled chess-board analysis JSON (like the 'Tiled Analysis Result')
into a FEN string.

Input format (per square):
{
  "square": "e1",          # standard algebraic notation, e.g. a1..h8
  "status": "Occupied" | "Empty",
  "piece_color": "White" | "Black" | null,
  "piece_type": "King" | "Queen" | "Rook" | "Bishop" | "Knight" | "Pawn" | null
}

NOTE: The "square" field is assumed to already be correct, standard
algebraic chess notation (a1-h8), regardless of which color is drawn
at the bottom of the rendered board image. The script does NOT need
to know board orientation for piece placement, since it places pieces
by their algebraic square name directly.
"""

import sys
from typing import Optional, Dict, List


PIECE_TO_FEN = {
    "king": "k",
    "queen": "q",
    "rook": "r",
    "bishop": "b",
    "knight": "n",
    "pawn": "p",
}

FILES = "abcdefgh"
RANKS = "12345678"


class FenConversionError(Exception):
    pass


def validate_square_name(square: str) -> None:
    """Validates if a given string is a valid chess square coordinate.

    Checks the type, length, file character, and rank character against standard 
    chess board dimensions.

    Args:
        square (str): The chess square coordinate to validate (e.g., 'e4').

    Raises:
        FenConversionError: If the square is not a string, does not have a 
            length of 2, or contains an invalid file or rank.
    """
    if (
        not isinstance(square, str)
        or len(square) != 2
        or square[0].lower() not in FILES
        or square[1] not in RANKS
    ):
        raise FenConversionError(f"Invalid square name encountered: {square!r}")


def piece_letter(piece_type: str, piece_color: str) -> str:
    """Converts a chess piece type and color into its standard FEN letter representation.

    Uppercase letters are used for white pieces, and lowercase letters are used 
    for black pieces.

    Args:
        piece_type (str): The name of the piece (e.g., 'king', 'pawn').
        piece_color (str): The color of the piece ('white' or 'black').

    Returns:
        str: The single-character FEN representation of the piece.

    Raises:
        FenConversionError: If the piece_type is not recognized or the 
            piece_color is invalid.
    """
    key = piece_type.strip().lower()
    if key not in PIECE_TO_FEN:
        raise FenConversionError(f"Unknown piece_type: {piece_type!r}")
    letter = PIECE_TO_FEN[key]
    color = piece_color.strip().lower()
    if color == "white":
        return letter.upper()
    elif color == "black":
        return letter
    else:
        raise FenConversionError(f"Unknown piece_color: {piece_color!r}")


def build_board(data: Dict) -> Dict:
    """Constructs a mapping of chess squares to their FEN piece letters.

    Processes raw square analysis data, validates the coordinates and piece 
    attributes thoroughly, and extracts the standard FEN representation 
    only for squares that are occupied.

    Args:
        data (dict): The raw structured dictionary containing chess board or 
            square analysis data.

    Returns:
        dict: A dictionary mapping square coordinates (e.g., 'e4') to their 
            corresponding single-character FEN piece letters (e.g., 'P', 'k').

    Raises:
        FenConversionError: If invalid square coordinates, unrecognized piece 
            types, or conflicting data structures are encountered.
    """
    squares = data.get("squares")
    if not isinstance(squares, list):
        raise FenConversionError("Input JSON must contain a 'squares' list.")

    board = {}
    seen = set()

    for entry in squares:
        if not isinstance(entry, dict):
            raise FenConversionError(f"Each square entry must be an object, got: {entry!r}")

        square = entry.get("square")
        status = entry.get("status")
        piece_color = entry.get("piece_color")
        piece_type = entry.get("piece_type")

        if square is None:
            raise FenConversionError(f"Square entry missing 'square' field: {entry!r}")

        square = square.lower()
        validate_square_name(square)

        if square in seen:
            raise FenConversionError(f"Duplicate square entry detected: {square!r}")
        seen.add(square)

        if status is None:
            raise FenConversionError(f"Square {square!r} missing 'status' field.")

        status_norm = status.strip().lower()

        if status_norm == "empty":
            if piece_color is not None or piece_type is not None:
                raise FenConversionError(
                    f"Square {square!r} marked Empty but has piece info "
                    f"(color={piece_color!r}, type={piece_type!r})."
                )
            continue

        if status_norm == "occupied":
            if not piece_color or not piece_type:
                raise FenConversionError(
                    f"Square {square!r} marked Occupied but missing piece_color/piece_type."
                )
            board[square] = piece_letter(piece_type, piece_color)
            continue

        raise FenConversionError(f"Unknown status value for square {square!r}: {status!r}")

    # Ensure we got a full 64-square board (warn, don't hard-fail, in case of partial input)
    expected = {f"{f}{r}" for f in FILES for r in RANKS}
    missing = expected - seen
    if missing:
        print(
            f"Warning: {len(missing)} square(s) missing from input and assumed empty: "
            f"{sorted(missing)}",
            file=sys.stderr,
        )

    return board


def board_to_placement_fen(board: Dict) -> str:
    """Builds the piece-placement field of the FEN string.

    Iterates through the board row by row starting from rank 8 down to rank 1, 
    and left to right from file a to h. Empty squares are aggregated into 
    consecutive integer counts according to standard FEN syntax.

    Args:
        board (dict): A dictionary mapping square coordinates (e.g., 'e4') to 
            their standard FEN letter representation (e.g., 'P', 'k').

    Returns:
        str: The complete piece-placement component of a FEN string 
            (e.g., 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR').
    """
    rows = []
    for rank in "87654321":  # FEN starts from rank 8 down to rank 1
        row_str = ""
        empty_run = 0
        for file in FILES:  # files a -> h left to right
            square = f"{file}{rank}"
            piece = board.get(square)
            if piece is None:
                empty_run += 1
            else:
                if empty_run:
                    row_str += str(empty_run)
                    empty_run = 0
                row_str += piece
        if empty_run:
            row_str += str(empty_run)
        rows.append(row_str)
    return "/".join(rows)


def validate_piece_counts(board: Dict) -> List:
    """Validates the board state for illegal or unusual chess piece counts.

    Checks that each player has exactly one king and no more than eight pawns, 
    generating descriptive warning strings for any violations found.

    Args:
        board (dict): A dictionary mapping square coordinates (e.g., 'e4') to 
            their standard FEN letter representation (e.g., 'K', 'p').

    Returns:
        list: A list of warning strings detailing any unusual or invalid 
            piece configurations. Returns an empty list if counts are legal.
    """
    warnings = []
    counts = {}
    for piece in board.values():
        counts[piece] = counts.get(piece, 0) + 1

    for color, king_letter in (("White", "K"), ("Black", "k")):
        n = counts.get(king_letter, 0)
        if n != 1:
            warnings.append(f"{color} king count is {n} (expected exactly 1).")

    for color, pawn_letter in (("White", "P"), ("Black", "p")):
        n = counts.get(pawn_letter, 0)
        if n > 8:
            warnings.append(f"{color} pawn count is {n} (expected at most 8).")

    return warnings

"""
def detect_castling_rights(board: dict) -> str:
    
    #Best-effort castling-rights detection based on whether king/rooks
    #are still sitting on their original squares. This is a heuristic,
    #not a guarantee (e.g. a rook could have moved away and back).

    rights = ""
    if board.get("e1") == "K":
        if board.get("h1") == "R":
            rights += "K"
        if board.get("a1") == "R":
            rights += "Q"
    if board.get("e8") == "k":
        if board.get("h8") == "r":
            rights += "k"
        if board.get("a8") == "r":
            rights += "q"
    return rights if rights else "-"
"""

"""
def json_to_fen(
    data: dict,
    active_color: str = "w",
    en_passant: str = "-",
    halfmove_clock: int = 0,
    fullmove_number: int = 1,
    auto_castling: bool = True,
    castling_override: Optional[str] = None,
) -> str:
    board = build_board(data)

    for warning in validate_piece_counts(board):
        print(f"Warning: {warning}", file=sys.stderr)

    placement = board_to_placement_fen(board)

    if active_color not in ("w", "b"):
        raise FenConversionError("active_color must be 'w' or 'b'.")

    if castling_override is not None:
        castling = castling_override
    elif auto_castling:
        castling = detect_castling_rights(board)
    else:
        castling = "-"

    fen = f"{placement} {active_color} {castling} {en_passant} {halfmove_clock} {fullmove_number}"
    return fen
"""

def dict_to_placement_fen(data: Dict) -> str:
    """Convenience one-shot function to convert raw analysis data to a FEN placement field.

    Takes a structured analysis dictionary, validates it, logs warnings for 
    unusual piece counts, and maps the squares to a standard FEN piece-placement 
    string spanning ranks 8-1 and files a-h.

    Args:
        data (dict): The raw analysis dictionary containing individual chess 
            board square states (e.g., {"squares": [...]}).

    Returns:
        str: The piece-placement FEN field string (e.g., 
            "rnb1kbnr/pp3ppp/2p1p3/8/2PqpP2/2N4N/PP1PB1PP/R1BQK2R").

    Raises:
        FenConversionError: If the input data contains structurally invalid or 
            unrecognized chess pieces/coordinates.
    """
    board = build_board(data)
    for warning in validate_piece_counts(board):
        print(f"Warning: {warning}", file=sys.stderr)
    return board_to_placement_fen(board)
