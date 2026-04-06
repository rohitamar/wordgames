import pronouncing

SIMILAR_VOWELS = [
    {"EH", "IH"},
    {"AE", "EH"},
    {"AA", "AH", "AO"},
    {"UH", "UW"},
    {"IH", "IY"},
]

def base_phoneme(p):
    if p[-1].isdigit():
        return p[:-1]
    return p

def vowels_match(v1, v2):
    b1 = base_phoneme(v1)
    b2 = base_phoneme(v2)

    if b1 == b2:
        return True

    for group in SIMILAR_VOWELS:
        if b1 in group and b2 in group:
            return True

    return False

def last_stressed_index(phonemes):
    for i in range(len(phonemes) - 1, -1, -1):
        if phonemes[i][-1] in "12":
            return i
    return -1

def rhyme_parts(phonemes):
    i = last_stressed_index(phonemes)
    if i == -1:
        return None
    return phonemes[i], tuple(phonemes[i + 1:])

def rhymes(w1, w2):
    p1_list = [p.split() for p in pronouncing.phones_for_word(w1)]
    p2_list = [p.split() for p in pronouncing.phones_for_word(w2)]

    for p1 in p1_list:
        r1 = rhyme_parts(p1)
        if r1 is None:
            continue
        v1, tail1 = r1
        for p2 in p2_list:
            r2 = rhyme_parts(p2)
            if r2 is None:
                continue
            v2, tail2 = r2
            if tail1 == tail2 and vowels_match(v1, v2):
                return True

    return False