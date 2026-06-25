#!/usr/bin/python3

# ChessLens Application
# Author: Yash Indane
# Email: <yashindane46@gmail.com>
# License: MIT

import argparse

from flask import Flask, render_template, request, jsonify
from src import board_to_json, fen_generation, move_generation


app = Flask(__name__)


@app.route('/chesslens')
def index():
    return render_template('capture.html')


@app.route('/analyse', methods=['POST'])
def analyse():
    """Handles the HTTP POST request to analyze a chessboard
    image and calculate the best move.

    Extracts the image file, player perspective, and calculation depth from
    the multipart form data. It tiles and evaluates the image to generate a 
    structured board state, converts that state into a Forsyth-Edwards Notation 
    (FEN) fragment, runs it through a chess engine, and returns the calculated 
    optimal move as a JSON response.

    Returns:
        Response: A Flask JSON response object containing the best calculated 
            move (e.g., {"best_move": "e2e4"}).
    """
    image = request.files['image']

    # 'white' or 'black'
    perspective = request.form['perspective']

    # 1-245
    depth = int(request.form['depth'])

    image.save('board.png')

    # generate FEN string
    board_json: dict = board_to_json.analyze_board_with_tiling(
        perspective, apikey, 'board.png'
    )

    fen_str: str = fen_generation.dict_to_placement_fen(board_json)

    # best move generation
    move: str = move_generation.calculate_move(fen_str, perspective, depth)

    return jsonify(best_move=move)


def parseargs() -> None:
    """Parse command line arguments"""
    global apikey

    parser = argparse.ArgumentParser(
        add_help="Argument parser for Plate-fetcher"
    )

    parser.add_argument('--apikey', help="OpenAI API Key", required=True)
    args = parser.parse_args()
    apikey = args.apikey


if __name__ == '__main__':
    parseargs()
    app.run(host='0.0.0.0', port=87)
