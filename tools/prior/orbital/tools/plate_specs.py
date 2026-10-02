"""Seedance plate specs. Plates are reference footage only: the renderer redraws them in pencil.

Prompts favour traceable pictures: hard directional light, clean silhouettes against black space,
readable motion, one clear action per plate. Reference images are addressed by their order.
"""
import pathlib, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import cfai

ROOT = pathlib.Path(__file__).resolve().parent.parent
R = {
    "LT": "media/chars/leonov_turnaround.png", "LF": "media/chars/leonov_faces.png",
    "BT": "media/chars/belyayev_turnaround.png", "BF": "media/chars/belyayev_faces.png",
    "SHIP": "media/env/env_voskhod2_orbit.png", "CAB": "media/env/env_capsule_interior.png",
    "TUBE": "media/env/env_volga_tube.png", "TAIGA": "media/env/env_taiga_landing.png",
}
_cache = {}


def ref(key):
    p = R.get(key, key)
    if p not in _cache:
        _cache[p] = cfai.data_uri(str(ROOT / p))
    return _cache[p]


LOOK = ("Photorealistic, shot on 35mm film, IMAX documentary realism in the spirit of Apollo 11 (2019) and Gravity. "
        "Accurate 1965 Soviet hardware: the white Berkut spacesuit with rust-orange harness straps, a white helmet with red CCCP letters above the visor, "
        "Soviet markings only. Hard directional sunlight, deep black space, crisp silhouettes. No on-screen text, no captions.")
LEO = "the cosmonaut Alexei Leonov (face and suit exactly as in the first two reference images)"
BEL = "the commander Pavel Belyayev (face and suit exactly as in his reference images)"

PLATES = {
    # ---------------- intro / hook 1 ----------------
    "hero_sunrise": dict(duration=10, refs=["LT", "LF", "SHIP"], prompt=
        f"{LEO} floats weightless in open space a few metres from the Voskhod-2 spacecraft (third reference), attached by a long coiled white umbilical tether. "
        "Orbital night: the Earth below is a dark disc with a thin glowing blue line along its horizon. After two seconds the sun breaks over the horizon behind him on the right: "
        "a blinding white-gold star, a thin layered band of red, orange, gold and blue light spreading along the curve of the atmosphere, and hard golden light sweeping across his suit. "
        "He slowly spreads his arms in wonder, drifting and turning a little. Slow steady camera push-in and gentle orbit around him. " + LOOK),
    "airlock_exit": dict(duration=8, refs=["LT", "LF", "SHIP"], prompt=
        f"Wide shot outside the Voskhod-2 spacecraft (third reference) in orbit. The outer hatch of the inflatable Volga airlock cylinder is open. {LEO} emerges from the airlock: "
        "first his helmet and shoulders, then he pushes gently off the rim and drifts out into the void, the white umbilical tether uncoiling behind him. "
        "The sunlit Earth fills the bottom of the frame, clouds and the Black Sea coast; black sky above. Locked-off camera with a very slow drift. " + LOOK),
    "glove_cu": dict(duration=5, refs=["LT", "LF"], prompt=
        f"Extreme close-up of the right glove of {LEO}'s white Berkut spacesuit floating against black space, the bright blue Earth out of focus far below. "
        "The fingers flex slowly and stiffly, fighting the pressure; the fabric of the glove and cuff swells and creases tighten as the suit inflates. "
        "Hard raking sunlight from the left, deep shadows. Macro lens, very slow push-in. " + LOOK),
    "visor_cu": dict(duration=6, refs=["LF", "LT"], prompt=
        f"Tight close-up of {LEO}'s face behind the clear visor of his white helmet (red CCCP above the visor) during the spacewalk. "
        "The curved glass reflects the blue Earth and the spacecraft. He breathes hard, a faint mist forms and fades on the inside of the visor, "
        "his eyes wide with wonder, then a flicker of worry as he realises he cannot feel his hands. Sunlight on one side of his face, the other side in shadow. Slow push-in. " + LOOK),
    "visor_sunrise": dict(duration=5, refs=["LF", "LT"], prompt=
        f"Extreme close-up on the curved visor of {LEO}'s white helmet. The orbital sunrise is reflected in the glass: a burst of white-gold light sweeps across the visor "
        "with thin bands of orange and blue; behind the reflection his eyes squint against the blaze and then widen. Golden light floods the helmet rim. Locked-off camera. " + LOOK),
    "ship_wide_sunrise": dict(duration=8, refs=["SHIP", "LT"], prompt=
        "Extremely wide shot: the Voskhod-2 spacecraft (first reference) small in the upper part of frame with a tiny cosmonaut in a white suit floating on a long tether beside it, "
        "above the enormous curve of the Earth. The sun sits exactly on the horizon: a thin layered arc of atmosphere glowing crimson, orange, gold, white and deep blue stretches along the whole limb. "
        "Clouds catch the first light. Very slow drift. " + LOOK),
    "reach_home": dict(duration=5, refs=["LT", "LF"], prompt=
        f"Over-the-shoulder shot of {LEO} floating in space, his right glove stretched toward the huge sunlit blue Earth below as if trying to touch it; "
        "the umbilical tether floats in a loose curve. Golden sunrise light from the right. Slow push-in past his shoulder toward the Earth. " + LOOK),
    # ---------------- swell / pre-chorus ----------------
    "camera_reach": dict(duration=6, refs=["LT", "LF"], prompt=
        f"Medium shot of {LEO} floating on his tether. He tries to reach down to a camera switch on his thigh, but his ballooned, rigid suit will not let him bend: "
        "his arm stops short, he strains, twists, tries again, and fails. The Earth rolls slowly behind him. Handheld documentary feel. " + LOOK),
    "suit_balloon": dict(duration=6, refs=["LT"], prompt=
        "Close-up detail of a white Berkut spacesuit in vacuum: the torso and knees visibly swell and stiffen as the suit balloons, the fabric pulls tight, the rust-orange harness straps strain "
        "and creak, the glove fingers splay apart. Hard sunlight, black background. Slow push-in along the suit. " + LOOK),
    "airlock_fail": dict(duration=8, refs=["LT", "LF", "SHIP"], prompt=
        f"{LEO} pulls himself hand over hand along the tether back to the open mouth of the Volga airlock cylinder (third reference). He tries to enter feet first, "
        "but his swollen rigid suit jams against the rim; he pushes back out, turns, struggles. Desperate, physical, the Earth wheeling below. Handheld camera close to the action. " + LOOK),
    "valve_bleed": dict(duration=6, refs=["LT", "LF"], prompt=
        f"Close-up: the gloved hand of {LEO} twists a small pressure valve on the sleeve of his white Berkut suit. Fine white wisps of escaping air hiss out into vacuum and vanish. "
        "Cut-in to his face behind the visor: sweat on his forehead, jaw clenched, eyes fixed, breathing in slow controlled breaths. Hard sunlight. " + LOOK),
    "tumble_slow": dict(duration=6, refs=["LT", "LF"], prompt=
        f"{LEO} drifts alone in slow motion, tumbling end over end at the full length of his tether, a lone white figure against the black void and the blue curve of the Earth. "
        "Eerie calm, like a slow dance. The camera slowly circles him. " + LOOK),
    "headfirst": dict(duration=6, refs=["LT", "LF", "SHIP"], prompt=
        f"From behind and slightly above: {LEO} dives head first into the narrow round opening of the Volga airlock cylinder, arms stretched ahead, "
        "squeezing his swollen suit through the rim, boots kicking, until only his legs remain outside. Hard sunlight, black space, the Earth below. " + LOOK),
    "tube_turn": dict(duration=8, refs=["TUBE", "LF", "LT"], prompt=
        f"Inside the narrow Volga airlock tube (first reference): {LEO} is crammed inside head first. Claustrophobic close shots: he twists and folds his body to turn around in a space barely wider than his shoulders, "
        "face drenched in sweat behind the visor, breathing hard. He finally reaches the outer hatch, grips the handle and pulls it shut; the light from outside narrows to a sliver and goes dark. " + LOOK),
    # ---------------- hook 2 / drop 1 ----------------
    "porthole_sunrise": dict(duration=6, refs=["CAB", "LF", "LT"], prompt=
        f"Inside the cramped Voskhod-2 capsule (first reference), close on {LEO}, helmet still on with the visor raised, exhausted and soaked in sweat, turning to a small round porthole. "
        "Through the porthole the orbital sunrise blazes: a white-gold sun on the curved horizon with thin bands of orange and blue. Golden light pours through the window across his face; "
        "he closes his eyes in relief. Symmetrical composition centred on the porthole. " + LOOK),
    "helmet_off": dict(duration=6, refs=["CAB", "LF", "LT", "BF"], prompt=
        f"Inside the Voskhod-2 capsule (first reference): {LEO} lifts off his white helmet, hair plastered with sweat, and lets it float; beside him {BEL} grips his shoulder. "
        "Warm light from the instrument panel and a porthole. Weightless details: a pencil and a loose cable drift past. Documentary close framing. " + LOOK),
    "airlock_jettison": dict(duration=6, refs=["SHIP"], prompt=
        "Exterior, low Earth orbit: the empty inflatable Volga airlock cylinder separates from the side of the Voskhod-2 spacecraft (reference) with a small puff of gas, "
        "and tumbles slowly away end over end toward the sunrise on the Earth's horizon, catching the golden light. The spacecraft stays in the foreground. Slow camera pan following the airlock. " + LOOK),
    "capsule_glide": dict(duration=8, refs=["SHIP"], prompt=
        "Exterior, low Earth orbit: the Voskhod-2 spacecraft (reference, airlock gone) glides steadily over the curved Earth from left to right toward the night side; "
        "the terminator line of darkness moves across the planet below, city lights beginning to appear, the thin blue atmosphere glowing on the horizon. Camera tracks alongside. " + LOOK),
    "leonov_turn": dict(duration=5, refs=["LF", "LT"], prompt=
        f"Studio portrait in motion: {LEO}, helmet off, in the white Berkut suit collar ring, turns his head from profile to face the camera and breaks into a warm, confident grin. "
        "Pure black background, a single hard key light from the upper left and a thin orange rim light. Centered, symmetrical, like a music-video member introduction. " + LOOK),
    "belyayev_turn": dict(duration=5, refs=["BF", "BT"], prompt=
        f"Studio portrait in motion: {BEL}, helmet off, in the white Berkut suit collar ring, turns his head from profile to face the camera with a calm, steady, serious look and a faint nod. "
        "Pure black background, a single hard key light from the upper left and a thin blue rim light. Centered, symmetrical, like a music-video member introduction. " + LOOK),
    "drawing_pencils": dict(duration=8, refs=["CAB", "LF", "LT"], prompt=
        f"Inside the Voskhod-2 capsule: {LEO}, gloves off, sketches on a small sheet of white paper pressed against his knee with a colored pencil. A bundle of colored pencils "
        "floats weightless around his wrist, each tied to a string on his wrist. On the paper: the curve of the Earth and a band of colors, the sunrise. Warm light from a porthole. "
        "Close-up of his hand and the paper, then a slow tilt up to his absorbed face. " + LOOK),
    "globus": dict(duration=5, refs=["CAB"], prompt=
        "Extreme close-up of the 'Globus' navigation instrument on the Voskhod-2 instrument panel (reference): a small metal-and-glass globe in a round window slowly rotating, "
        "brass meridian rings, a tiny crosshair marking the spacecraft's position, dials and toggle switches around it lit by warm panel lamps. Slow push-in. " + LOOK),
    # ---------------- build / hook 3 ----------------
    "red_warning": dict(duration=6, refs=["CAB", "BF", "LF"], prompt=
        f"Inside the Voskhod-2 capsule: a red warning lamp on the instrument panel starts flashing, bathing the cramped cabin in pulsing red light. {BEL} and {LEO} snap their heads toward the panel, "
        "alarmed, then exchange a look. Needles on the dials swing. Tense handheld close-ups. " + LOOK),
    "vzor_manual": dict(duration=8, refs=["CAB", "BF", "LF", "LT"], prompt=
        f"Inside the Voskhod-2 capsule, the first manual re-entry: {BEL} has left his seat and lies stretched across both seats on his side, his face pressed to the round Vzor optical porthole in the floor "
        f"to line the ship up with the horizon, while {LEO} braces him and holds him in place with both arms. Sunlight spins slowly across them through the porthole. Cramped, sweaty, concentrated. " + LOOK),
    "retrofire": dict(duration=5, refs=["SHIP"], prompt=
        "Exterior, low Earth orbit, close on the rear of the Voskhod-2 spacecraft (reference, airlock gone): the retro-rocket engine ignites with a violent orange flame and white exhaust plume, "
        "the whole spacecraft shudders and begins to fall toward the curved Earth below. Night side of the planet, the flame lighting the hull. " + LOOK),
    "capsule_spin": dict(duration=6, refs=["SHIP"], prompt=
        "Exterior: the spherical Voskhod-2 descent capsule has separated from the instrument module but is still tethered to it by a bundle of cables; the two pieces whirl around each other, "
        "spinning wildly, above the curved Earth, the sun flashing past on every turn. Then the cables burn through and the capsule tumbles free. Dramatic, chaotic motion. " + LOOK),
    "g_force": dict(duration=6, refs=["CAB", "LF", "BF"], prompt=
        f"Inside the Voskhod-2 capsule during re-entry: {LEO} and {BEL} are crushed back into their seats by ten g of deceleration, faces pulled and distorted, teeth clenched, the cabin vibrating violently. "
        "Through the small porthole, orange plasma fire roars past, flooding the cabin with flickering orange light. " + LOOK),
    "reentry_fire": dict(duration=8, refs=["SHIP"], prompt=
        "Exterior, re-entry: the spherical Voskhod-2 descent capsule (reference) plunges into the upper atmosphere, heat shield first, wrapped in a blazing envelope of orange, gold and white plasma, "
        "a long glowing trail of fire and sparks streaming behind it, the dark curve of the Earth below. The capsule shakes and burns like a falling star. Camera tracks with it. " + LOOK),
    # ---------------- drop 2 / outro ----------------
    "parachute": dict(duration=8, refs=["TAIGA", "SHIP"], prompt=
        "High in a pale grey-blue sky above a layer of clouds: the scorched spherical Voskhod-2 capsule swings beneath a huge orange-and-white striped parachute that has just blossomed open, "
        "the canopy billowing and snapping full, lines taut, the capsule pendulum-swinging. Camera circles the parachute from below. " + LOOK),
    "descent_forest": dict(duration=10, refs=["TAIGA"], prompt=
        "Aerial view looking down past the orange-and-white parachute canopy and the swinging spherical capsule toward an endless snow-covered Ural taiga forest, "
        "dark fir trees and white snow as far as the horizon, no roads, no clearings, overcast March light. Slow spiralling descent, the trees getting closer. " + LOOK),
    "treetops": dict(duration=5, refs=["TAIGA"], prompt=
        "The spherical Voskhod-2 capsule under its parachute drops toward snowy fir treetops; at the last moment its soft-landing rockets fire with a burst of flame and snow, "
        "and it crashes down between two tall firs into deep snow, snow exploding up in a white cloud, branches whipping. Low angle from the snow. " + LOOK),
    "hatch_exit": dict(duration=8, refs=["TAIGA", "LF", "LT"], prompt=
        f"Deep snow in the silent Ural taiga at dusk, the scorched Voskhod-2 capsule (first reference) lying between fir trees. Its round hatch pops open; {LEO}, helmet off, climbs out "
        "and sinks thigh-deep into the snow, breath steaming, looking around at the endless forest. Snow drifting down. " + LOOK),
    "two_men_snow": dict(duration=7, refs=["TAIGA", "LF", "LT", "BF"], prompt=
        f"The Ural taiga at dusk: {LEO} and {BEL} stand in deep snow beside the scorched capsule and the parachute draped in the trees, in their white suits, breath steaming. "
        "They look up at the darkening sky, then at each other, and laugh with exhausted relief; Leonov claps Belyayev on the shoulder. Snowflakes falling. " + LOOK),
    "fire_night": dict(duration=8, refs=["TAIGA", "LF", "BF"], prompt=
        f"Night in the frozen taiga: {LEO} and {BEL}, wrapped in pieces of the orange parachute, sit close to a small crackling fire in the snow beside the dark capsule. "
        "Beyond the firelight, between black tree trunks, pairs of wolves' eyes glint in the darkness. Sparks rise into falling snow. " + LOOK),
    "drawing_survives": dict(duration=6, refs=["TAIGA", "LF", "LT"], prompt=
        f"By firelight in the snowy forest at night, {LEO} pulls a small folded sheet of paper from inside his suit, unfolds it with stiff cold fingers and looks at it: "
        "a colored-pencil drawing of an orbital sunrise, bands of color over the curve of the Earth. He smiles. Close-up on his hands and the drawing, then his face. " + LOOK),
    "rescue": dict(duration=8, refs=["TAIGA", "LF", "BF"], prompt=
        "Morning in the snowy Ural taiga: a helicopter hovers over the treetops dropping supplies in a swirl of snow, while rescuers on skis in dark winter coats glide between the firs "
        "toward two cosmonauts in white suits standing by the capsule, waving. Joyful, cold, bright overcast light. " + LOOK),
}

# ---------------- the singer (Jade, now) — lip-sync plates: the song segment is the audio reference ----------------
R.update({"JT": "media/chars/jade_turnaround.png", "JF": "media/chars/jade_faces.png", "JS": "media/chars/jade_src/Sheet_1_Jade_now.jpg"})
JADE = ("the singer (the woman in the first two reference images: long messy dark hair in a loose high ponytail with strands framing her face, "
        "oversized heather-grey hoodie)")
SING = ("She sings the song in the reference audio, her lips precisely synchronised to every word and breath of the vocal from the first frame to the last; "
        "natural singing mouth shapes, jaw and throat movement.")
LOOK_NOW = ("Photorealistic, shot on 35mm film, cinematic, present day San Francisco. Clear readable face, hard directional light, simple uncluttered background. "
            "No on-screen text, no captions.")
PLATES.update({
    "jade_hook1": dict(duration=5, refs=["JT", "JF", "JS"], audio=["media/audio_refs/jade_hook1.mp3"], generate_audio=True, prompt=
        f"Dawn on a grassy hilltop above San Francisco, the city and the bay far below in low fog. Close-up of {JADE}, facing the rising sun, golden sunrise light on her face, "
        f"wind in loose strands of hair. {SING} She lifts her eyes to the sky on the last word. Slow push-in. " + LOOK_NOW),
    "jade_hook2": dict(duration=5, refs=["JT", "JF", "JS"], audio=["media/audio_refs/jade_hook2.mp3"], generate_audio=True, prompt=
        f"Night, a small cluttered room: {JADE} sits at her desk facing the camera, a warm desk lamp beside her, colored pencils and drawings of a 1960s cosmonaut spread on the desk, "
        f"a dark window with distant city lights behind her. She looks up from her drawing straight toward the lens and sings, clearly and openly mouthing every word. {SING} "
        f"Frontal medium close-up, her whole face visible and lit by the warm lamp, deep shadows around. " + LOOK_NOW),
    "jade_brk": dict(duration=8, refs=["JT", "JF", "JS"], audio=["media/audio_refs/jade_brk.mp3"], generate_audio=True, prompt=
        f"Sunset on the same grassy hilltop above San Francisco: the whole sky has turned deep red and orange. {JADE} stands facing the sky, singing, "
        f"then slowly raises one open hand toward the sky as if reaching for something she can't touch. {SING} Medium close-up, low angle, the red sky behind her, strong rim light. " + LOOK_NOW),
    "jade_art": dict(duration=12, refs=["JS", "JT", "JF"], audio=["media/audio_refs/jade_art.mp3"], generate_audio=True, prompt=
        f"Night at her desk by a window where snow is falling outside: {JADE} draws with colored pencils on a sheet of white paper, sketching the curved horizon of the Earth and a band of sunrise colors. "
        f"She sings softly and intimately while drawing, sometimes looking at her hands. {SING} Alternate between a close-up of her face lit by the warm desk lamp and her hands drawing. " + LOOK_NOW),
    "jade_hook3": dict(duration=12, refs=["JT", "JF", "JS"], audio=["media/audio_refs/jade_hook3.mp3"], generate_audio=True, prompt=
        f"Twilight on the grassy hilltop above San Francisco, just after sunset: the sky is deep blue fading to pale gold along the Pacific horizon, the city below calm with evening lights. "
        f"Far away over the ocean a small rocket climbs on a thin, bright white-gold exhaust trail that arcs high into the sky; high up, still lit by the sun, the exhaust fans out into a delicate, "
        f"translucent, glowing feather of blue and white light like a comet's tail. Peaceful and awe-inspiring: no explosion, no fireball, no smoke clouds, nothing on fire. "
        f"{JADE} stands in the foreground singing with full power, face lifted toward the rocket's trail, lit by the cool twilight. {SING} Medium close-up with the rocket trail behind her, slow push-in. " + LOOK_NOW),
    "jade_hands": dict(duration=8, refs=["JT", "JS"], prompt=
        "Overhead close-up of a woman's hands (grey hoodie sleeves pushed up) drawing with colored pencils on a sheet of white paper on a wooden desk at night under a warm lamp: "
        "she draws the curved horizon of the Earth, then quick strokes of red, orange, yellow and blue along it — an orbital sunrise. Loose colored pencils around the paper. "
        "Steady overhead camera. Photorealistic, 35mm film, no text."),
})
