#!/usr/bin/env python3
"""Round-9 stills (gpt-image-2, ONE input image each to stay under the ~30 s proxy cut).
  round9.py stopff N K0   -> assets/character/anime/v2/cands/stopff_<k>.jpg   (edit of shots/J5_v3.jpg: siren rim -> soft night light, plain dark bg)
  round9.py committee N K0 -> assets/character/anime/v2/cands/committee_<k>.jpg (composite board: v3 sheet + canon head + defense_room/1)
Log: assets/character/anime/v2/prompts.json"""
import sys, os
sys.path.insert(0, "/home/user/rewind-music-video/tools/anime")
import jacket_v2 as JV
from shots import STYLE
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
A = JV.A; ROOT = JV.ROOT

def committee_board():
    c = Image.new("RGB", (1536, 1024), (240, 240, 238))
    c.paste(Image.open(A + "/CANON_SHEET_v3.jpg").convert("RGB").crop((0, 0, 768, 1024)), (0, 0))
    c.paste(Image.open(A + "/CANON_HEAD_front.jpg").convert("RGB").resize((448, 448)), (768 + 160, 20))
    pl = Image.open(ROOT + "/assets/sets/defense_room/1.jpg").convert("RGB").resize((768, 432)); c.paste(pl, (768, 1024 - 432 - 20))
    p = A + "/v2/committee_board.jpg"; c.save(p, quality=92); return p

STOP = ("Edit this anime film frame. Keep her face EXACTLY (same eyes and their size, same expression), hair, pose, framing, outfit "
        "(white cropped jacket with open band collar, orange bands, pale-blue dot patch, '1420 MHz' patch on her LEFT sleeve, black "
        "mock-neck crop top) and art style. Change ONLY the lighting and background: remove the red and blue police-siren rim lights "
        "completely; she is lit by a soft, cool, even night light from the front-left (gentle moonlight-blue key, soft fill, a faint "
        "cool rim on her hair), clean and youthful, no harsh shadows on the face. The background is a plain, uniform, very dark "
        "blue-black void with no lights, no gradients, no objects, so she separates cleanly from it. No text.")
COMM = (
  "The input is a reference board: LEFT = the official model sheet of the character (front and three-quarter view), TOP-RIGHT = "
  "her face close-up, BOTTOM-RIGHT = a photo of the location (a dark university seminar room). Draw ONE new anime film frame (not a "
  "board), 16:9, in the same anime art style as the sheet (clean thin lineart, flat cel shading): the dissertation-defense room, a "
  "long committee table seen straight on from the front, facing the camera, a dark chalkboard behind, a projector beam cutting "
  "through the dark from frame-left. Seated in a row behind the table, all facing roughly toward the camera: EIGHT copies of this "
  "SAME woman - every one has exactly her face (same large dark-brown eyes, same face shape), her long straight black center-parted "
  "hair with curtain bangs, and her white cropped jacket with orange bands and black top - but each one acting differently, left to "
  "right: (1) taking notes with a pen, head down; (2) staring blankly into space; (3) arms crossed, skeptical, one eyebrow raised; "
  "(4) asleep, head propped on her hand, eyes closed; (5) wearing thin round glasses, reading a stapled thesis; (6) eating a snack "
  "from a small bag; (7) smiling knowingly straight at the camera, fingers steepled; (8) same jacket but in pale mint-green instead of "
  "white, chin on fist, bored. Each has a small paper name card on the table in front of her, all left blank. Even, soft, dim "
  "lighting on all faces so every face reads clearly; cool projector light; faint red/blue glow at the window on the right. All "
  "eight are the same size and fully visible from the chest up above the table. FRAMING: a close medium-wide shot from just "
  "behind the near edge of the table at seated eye height - the eight women fill the whole width of the frame shoulder to "
  "shoulder, their heads in the upper-middle of the frame and LARGE (each face clearly readable), the table top only in the "
  "bottom quarter of the frame; little empty wall above them. No text anywhere.")

COMM2 = (
  "Edit this anime film frame. Keep the room, camera, framing, the table, the name cards, the lighting and every woman's position, "
  "pose, size, jacket and FACE exactly as they are (same face for all of them: same large dark-brown eyes, same face shape - they "
  "are all the same woman). Change ONLY these hairstyles / props, counting the eight women from LEFT to RIGHT: "
  "(1) the note-taker: a long sleek black BOB (straight, chin-to-collarbone length, blunt ends) instead of long hair; "
  "(2) the blank-staring one: a short PURPLE pixie cut (cropped short, violet-purple); "
  "(3) the arms-crossed one: shoulder-length straight black hair with a bright TEAL under-layer visible underneath; "
  "(4) the one asleep on her hand: unchanged; (5) the one with glasses reading the thesis: unchanged; "
  "(6) the snacking one: MERMAID WAVES - shoulder-length wavy hair in blended blue, green and purple; "
  "(7) the knowing smile with steepled fingers: unchanged; "
  "(8) the one in the mint-green jacket: she is now CHEWING GUM, blowing a small round pink bubble-gum bubble from her lips, her "
  "chin still on her fist. Same anime art style, clean lineart, flat cel shading. No text.")

COMM3 = (
  "Edit this anime film frame minimally. Keep the room, camera, framing, table, name cards, lighting and every woman's position, "
  "pose, jacket, props and FACE exactly as they are (same face, same eyes and their size). Change ONLY three things, counting the "
  "eight women from LEFT to RIGHT: (1) the note-taker's straight black bob becomes slightly longer - just past the jaw, reaching "
  "toward the collarbone (a subtle change, same style); (2) the purple-haired one: her short purple pixie becomes a messy, tousled "
  "purple bob of about the same length as woman 1's (chin-to-collarbone), still violet-purple; (4) the sleeping one: she is "
  "asleep with her head resting on her folded arms lying directly on the table, her face turned to the side toward the camera and "
  "partly visible, eyes closed, long black hair spilling over her arms - no longer propped on her hand. Everything else identical. "
  "Same anime art style. No text.")

if __name__ == "__main__":
    job, n, k0 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    src, prompt = {"stopff": lambda: (A + "/shots/J5_v3.jpg", STOP), "committee": lambda: (committee_board(), COMM),
                   "committee2": lambda: (A + "/committee_ff.jpg", COMM2),
                   "committee3": lambda: (A + "/committee_v2_ff.jpg", COMM3)}[job]()
    with ThreadPoolExecutor(4) as ex:
        for k in range(n): ex.submit(JV.one, job, src, prompt, "1536x1024", k0 + k, "medium")
