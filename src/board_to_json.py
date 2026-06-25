import io
import os
import json
import base64

from PIL import Image
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Tuple, Dict, Literal, Optional


class SquareAnalysis(BaseModel):
    """Analysis results for an individual square on a chess board.

    Attributes:
        square (str): The coordinate of the square being analyzed (e.g., 'e4').
        status (Literal["Occupied", "Empty"]): Status indicating whether the 
            square contains a chess piece or is an empty background tile.
        piece_color (Optional[Literal["White", "Black"]]): The color of the 
            piece if the square is occupied. Defaults to None.
        piece_type (Optional[Literal["King", "Queen", "Rook", "Bishop", "Knight", "Pawn"]]): 
            The type of the chess piece if the square is occupied. Defaults to None.
    """

    square: str = Field(
        description="The coordinate of the square being analyzed (e.g., 'e4')."
    )
    status: Literal["Occupied", "Empty"] = Field(
        description="Set to 'Empty' if the image is a solid background tile. Set to 'Occupied' ONLY if a chess piece icon is present."
    )
    piece_color: Optional[Literal["White", "Black"]] = Field(
        default=None, description="Color of the piece if occupied."
    )
    piece_type: Optional[
        Literal["King", "Queen", "Rook", "Bishop", "Knight", "Pawn"]
    ] = Field(default=None, description="Type of the chess piece if occupied.")


class ChessBoardCompleteAnalysis(BaseModel):
    """Complete structural analysis of an entire chess board state.

    Attributes:
        squares (list[SquareAnalysis]): A list containing individual analysis 
            data for all 64 squares on the chess board.
    """

    squares: list[SquareAnalysis] = Field(
        description="The complete list of all 64 squares analyzed individually."
    )


def slice_and_encode_board(
    image_path: str,
    perspective: str = "white",
) -> List[Tuple[str, str]]:
    """Slices the chessboard into 64 individual squares and encodes them to base64.

    Adjusts coordinate mapping based on the player's perspective.

    Args:
        image_path (str): The file path to the chessboard image.
        perspective (str): The player's orientation view, either "white" or 
            "black". Defaults to "white".

    Returns:
        List[Tuple[str, str]]: A list of tuples, where each tuple contains the 
            square coordinate (e.g., 'e4') and its corresponding base64 encoded image string.
    """
    img = Image.open(image_path).convert("RGB")
    img = img.resize((512, 512), Image.LANCZOS)
    width, height = img.size

    square_w = width / 8
    square_h = height / 8

    # Dynamically adjust orientation based on who is at the bottom
    if perspective.lower() == "black":
        # From top to bottom of image: Rank 1 up to Rank 8
        # From left to right of image: File h down to File a
        ranks = ["1", "2", "3", "4", "5", "6", "7", "8"]
        files = ["h", "g", "f", "e", "d", "c", "b", "a"]
    else:
        # Default: White at the bottom
        # From top to bottom of image: Rank 8 down to Rank 1
        # From left to right of image: File a up to File h
        ranks = ["8", "7", "6", "5", "4", "3", "2", "1"]
        files = ["a", "b", "c", "d", "e", "f", "g", "h"]

    tiles = []

    for r_idx, rank in enumerate(ranks):
        for f_idx, file in enumerate(files):
            left = f_idx * square_w
            top = r_idx * square_h
            right = (f_idx + 1) * square_w
            bottom = (r_idx + 1) * square_h

            square_img = img.crop((left, top, right, bottom))

            buffered = io.BytesIO()
            square_img.save(buffered, format="PNG")
            b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            square_label = f"{file}{rank}"
            tiles.append((square_label, b64_str))

    return tiles


def analyze_board_with_tiling(
    perspective: str,
    apikey: str,
    image_path: str='board.png',
) -> Dict:
    """Analyzes a chess board image by breaking it into individual square tiles.

    Args:
        perspective (str): The board orientation view (e.g., 'white' or 'black').
        apikey (str): The OpenAI API key used to initialize the client.
        image_path (str): Path to the chessboard image file. Defaults to 'board.png'.

    Returns:
        Dict: A dictionary containing the structural analysis of the board state.
    """
    client = OpenAI(api_key=apikey)

    if not os.path.exists(image_path):
        print(f"Error: The file at {image_path} could not be found.")
        return

    print(
        f"Slicing chessboard into 64 isolated squares (Perspective: {perspective})..."
    )
    tiles = slice_and_encode_board(image_path, perspective=perspective)

    prompt = (
    "You are a high-precision chess vision engine. You are provided with 64 individual cropped images "
    "representing every single square of a chessboard. Analyze each image independently.\n\n"
    "CRITICAL RULES:\n"
    "1. Focus entirely on the CENTER of the image. If the image contains ONLY a solid background color "
    "(or solid yellow highlight) with no piece icon on top of it, its status MUST be 'Empty'.\n"
    "2. Do not infer pieces based on context; evaluate only the pixels inside that specific cropped square.\n"
    "3. Ignore any tiny board coordinate markers (letters/numbers) that may appear on the extreme edges of outer squares.\n"
    "4. A piece is only present if a COMPLETE or MAJORITY of a chess piece icon is clearly visible in the CENTER of the image. "
    "Partial edges, shadows, or slight overhangs from neighboring squares must be ignored and treated as Empty.\n"
    "5. When in doubt between Occupied and Empty, choose Empty."
    )

    message_content = [{"type": "text", "text": prompt}]

    for square_label, b64_str in tiles:
        message_content.append({"type": "text", "text": f"Square: {square_label}"})
        message_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64_str}",
                    "detail": "low",
                },
            }
        )

    print("Sending isolated tiles to gpt-5.4-mini...")

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-5.4-mini",
            messages=[{"role": "user", "content": message_content}],
            response_format=ChessBoardCompleteAnalysis,
            temperature=0.0,
            #max_tokens=2000,
        )

        result = completion.choices[0].message.parsed
        print(f"\n--- Tiled Analysis Result ({perspective.capitalize()} Bottom) ---")
        res = result.model_dump_json(indent=2)
        print(res)
        return json.loads(res)

    except Exception as e:
        print(f"An error occurred: {e}")
