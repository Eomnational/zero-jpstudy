"""Hepburn-style kana transliteration for reading aids (not phonetic IPA)."""
BASE = dict(zip(
    'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ',
    'a i u e o ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no ha hi fu he ho ma mi mu me mo ya yu yo ra ri ru re ro wa o n ga gi gu ge go za ji zu ze zo da ji zu de do ba bi bu be bo pa pi pu pe po'.split()
))
DIGRAPHS = {}
for kana, stem in [('き','ky'),('し','sh'),('ち','ch'),('に','ny'),('ひ','hy'),('み','my'),('り','ry'),('ぎ','gy'),('じ','j'),('び','by'),('ぴ','py'),('ぢ','j')]:
    for small, vowel in [('ゃ','a'),('ゅ','u'),('ょ','o')]: DIGRAPHS[kana+small] = stem+vowel
DIGRAPHS.update({'しゃ':'sha','しゅ':'shu','しょ':'sho','ちゃ':'cha','ちゅ':'chu','ちょ':'cho','じゃ':'ja','じゅ':'ju','じょ':'jo','ぢゃ':'ja','ぢゅ':'ju','ぢょ':'jo'})
for first, stem in [('ふ','f'),('ヴ','v'),('て','t'),('で','d'),('と','t'),('ど','d'),('う','w'),('し','sh'),('ち','ch'),('じ','j')]:
    for small, vowel in [('ぁ','a'),('ぃ','i'),('ぅ','u'),('ぇ','e'),('ぉ','o')]:
        DIGRAPHS.setdefault(first+small,stem+vowel)
DIGRAPHS.update({'てぃ':'ti','でぃ':'di','とぅ':'tu','どぅ':'du','うぃ':'wi','うぇ':'we','うぉ':'wo','ふぁ':'fa','ふぃ':'fi','ふぇ':'fe','ふぉ':'fo','しぇ':'she','ちぇ':'che','じぇ':'je'})

def romanize(text):
    s=''.join(chr(ord(c)-96) if 'ァ'<=c<='ヶ' else c for c in text)
    out=[]; i=0
    while i<len(s):
        c=s[i]
        if c=='っ' and i+1<len(s):
            nxt=DIGRAPHS.get(s[i+1:i+3]) or BASE.get(s[i+1],'')
            out.append('t' if nxt.startswith('ch') else nxt[:1]);i+=1;continue
        if c=='ー':
            if out:
                vowel=next((x for x in reversed(''.join(out)) if x in 'aeiou'), '')
                out.append(vowel)
            i+=1;continue
        if c=='ん':
            nxt=DIGRAPHS.get(s[i+1:i+3]) or BASE.get(s[i+1:i+2],'')
            out.append("n'" if nxt.startswith(('a','i','u','e','o','y','n')) else 'n');i+=1;continue
        pair=s[i:i+2]
        if pair in DIGRAPHS: out.append(DIGRAPHS[pair]);i+=2;continue
        out.append(BASE.get(c, {'～':'~','〜':'~','／':' / ','・':' · '}.get(c,c)))
        i+=1
    return ''.join(out)
