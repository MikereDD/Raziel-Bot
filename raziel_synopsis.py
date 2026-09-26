# --------------------------------------------
# file:     raziel_synopsis.py
# author:   Typezer∅
# feature:  Synopsis foundation
# desc:     Caption-first transcript extraction
#           and local synopsis generation.
# --------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from html import unescape
import json
import math
import re
from pathlib import Path
from typing import Protocol
from urllib.request import Request, urlopen

import yt_dlp


class SynopsisError(RuntimeError):
    """Expected synopsis/caption failure suitable for user-facing reporting."""


@dataclass(slots=True)
class CaptionTrack:
    language: str
    source: str
    ext: str
    url: str


@dataclass(slots=True)
class SynopsisResult:
    title: str
    uploader: str
    duration: int | None
    language: str
    caption_source: str
    transcript_chars: int
    transcript_words: int
    synopsis: str


class Summarizer(Protocol):
    """Backend boundary for future LLM/local-model summarizers."""

    def summarize(self, text: str, *, title: str = "") -> str:
        ...


_TIMESTAMP_RE = re.compile(
    r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3}\s+-->\s+"
    r"(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3}"
)
_TAG_RE = re.compile(r"<[^>]+>")
_BRACKET_NOISE_RE = re.compile(
    r"\[(?:music|applause|laughter|laughs|cheering|silence|noise|inaudible|crosstalk|foreign)\]",
    re.IGNORECASE,
)
_SPEAKER_ARROW_RE = re.compile(r"(?:^|\s)(?:>>+|»+)(?=\s|$)")
_WS_RE = re.compile(r"\s+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]{1,}")
_VTT_CONTROL_RE = re.compile(r"^(?:WEBVTT|Kind:|Language:|NOTE\b|STYLE\b|REGION\b)")
_CUE_ID_RE = re.compile(r"^\d+$")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
    "could", "did", "do", "does", "for", "from", "had", "has", "have", "he",
    "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "just", "may", "me", "more", "most", "my", "no", "not", "of",
    "on", "or", "our", "out", "she", "so", "some", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "to",
    "too", "up", "us", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your",
}


def _language_rank(language: str) -> tuple[int, str]:
    lang = (language or "").lower().replace("_", "-")
    if lang == "en":
        return (0, lang)
    if lang.startswith("en-"):
        return (1, lang)
    if lang.startswith("en"):
        return (2, lang)
    return (100, lang)


def _format_rank(ext: str) -> int:
    return {
        "vtt": 0,
        "srt": 1,
        "json3": 2,
        "srv3": 3,
        "ttml": 4,
    }.get((ext or "").lower(), 50)


def _pick_track_from_group(
    tracks: dict,
    *,
    source: str,
) -> CaptionTrack | None:
    english = sorted(
        ((lang, entries) for lang, entries in (tracks or {}).items()
         if _language_rank(lang)[0] < 100),
        key=lambda item: _language_rank(item[0]),
    )

    for language, entries in english:
        candidates = []
        for entry in entries or []:
            url = str(entry.get("url") or "").strip()
            if not url:
                continue
            ext = str(entry.get("ext") or "").lower()
            candidates.append((_format_rank(ext), ext, url))

        if candidates:
            _, ext, url = min(candidates, key=lambda item: item[0])
            return CaptionTrack(
                language=language,
                source=source,
                ext=ext,
                url=url,
            )

    return None


def choose_caption_track(info: dict) -> CaptionTrack:
    # Human English subtitles first.
    track = _pick_track_from_group(info.get("subtitles") or {}, source="human")
    if track:
        return track

    # Then English automatic captions.
    track = _pick_track_from_group(
        info.get("automatic_captions") or {},
        source="automatic",
    )
    if track:
        return track

    human_langs = sorted((info.get("subtitles") or {}).keys())
    auto_langs = sorted((info.get("automatic_captions") or {}).keys())

    available = []
    if human_langs:
        available.append("human: " + ", ".join(human_langs[:12]))
    if auto_langs:
        available.append("auto: " + ", ".join(auto_langs[:12]))

    suffix = f" Available tracks: {'; '.join(available)}." if available else ""
    raise SynopsisError("No English captions are available for this video." + suffix)


def _download_text(url: str, *, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/153 Safari/537.36"
            )
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except Exception as exc:
        raise SynopsisError(f"Could not download caption track: {exc}") from exc

    return raw.decode("utf-8", errors="replace")


def _normalize_caption_line(line: str) -> str:
    line = unescape(line)
    line = _TAG_RE.sub("", line)
    line = _BRACKET_NOISE_RE.sub(" ", line)
    line = _SPEAKER_ARROW_RE.sub(" ", line)
    line = line.replace("\u200b", "")
    line = _WS_RE.sub(" ", line).strip(" -–—")
    return line


def _caption_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0

    a = _WS_RE.sub(" ", left.lower()).strip()
    b = _WS_RE.sub(" ", right.lower()).strip()

    if a == b:
        return 1.0

    a_words = set(_WORD_RE.findall(a))
    b_words = set(_WORD_RE.findall(b))
    jaccard = (
        len(a_words & b_words) / max(len(a_words | b_words), 1)
        if a_words and b_words
        else 0.0
    )
    sequence = SequenceMatcher(None, a, b).ratio()
    return max(jaccard, sequence)


def clean_vtt_or_srt(raw: str) -> str:
    """Convert VTT/SRT captions to deduplicated plain transcript text."""

    lines: list[str] = []

    for raw_line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()

        if not line:
            continue
        if _VTT_CONTROL_RE.match(line):
            continue
        if _TIMESTAMP_RE.match(line):
            continue
        if _CUE_ID_RE.match(line):
            continue
        if line.startswith("X-TIMESTAMP-MAP"):
            continue

        line = _normalize_caption_line(line)
        if not line:
            continue

        if lines:
            previous = lines[-1]

            if line.startswith(previous) and len(line) > len(previous):
                lines[-1] = line
                continue

            if previous.startswith(line):
                continue

            if _caption_similarity(previous, line) >= 0.90:
                if len(line) > len(previous):
                    lines[-1] = line
                continue

        lines.append(line)

    text = " ".join(lines)
    text = _WS_RE.sub(" ", text).strip()
    return text


def clean_json3(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SynopsisError("Caption JSON could not be parsed.") from exc

    parts: list[str] = []
    previous = ""

    for event in payload.get("events") or []:
        segs = event.get("segs") or []
        text = "".join(str(seg.get("utf8") or "") for seg in segs)
        text = _normalize_caption_line(text.replace("\n", " "))

        if not text or text == previous:
            continue

        parts.append(text)
        previous = text

    return _WS_RE.sub(" ", " ".join(parts)).strip()


def clean_caption_text(raw: str, ext: str) -> str:
    if (ext or "").lower() == "json3":
        text = clean_json3(raw)
    else:
        text = clean_vtt_or_srt(raw)

    if len(text) < 80:
        raise SynopsisError("The caption track was empty or too short to summarize.")
    return text


def chunk_transcript(text: str, max_chars: int = 9000) -> list[str]:
    """
    Split a transcript on sentence boundaries while keeping chunks reasonably
    sized. This is intentionally backend-neutral for future LLM summarizers.
    """

    sentences = split_sentences(text)
    if not sentences:
        return [text] if text else []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        add_len = len(sentence) + (1 if current else 0)

        if current and current_len + add_len > max_chars:
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += add_len

    if current:
        chunks.append(" ".join(current))

    return chunks


def split_sentences(text: str) -> list[str]:
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return []

    sentences = [
        s.strip()
        for s in _SENTENCE_RE.split(text)
        if len(s.strip()) >= 24
    ]

    # Caption text frequently lacks punctuation. Fall back to bounded blocks.
    if len(sentences) <= 1 and len(text) > 500:
        words = text.split()
        sentences = []
        for start in range(0, len(words), 45):
            block = " ".join(words[start:start + 45]).strip()
            if block:
                sentences.append(block)

    return sentences


class ExtractiveSummarizer:
    """
    Dependency-free baseline summarizer.

    The goal is not to imitate an LLM. It selects a small set of distinct,
    information-dense transcript sentences while avoiding adjacent/repetitive
    caption fragments. A future local LLM backend can replace this class
    without changing caption extraction or Telegram command handling.
    """

    def __init__(self, max_sentences: int = 5, max_chars: int = 2000):
        self.max_sentences = max_sentences
        self.max_chars = max_chars

    @staticmethod
    def _content_words(text: str) -> list[str]:
        return [
            w.lower()
            for w in _WORD_RE.findall(text)
            if w.lower() not in _STOPWORDS and len(w) > 2
        ]

    @classmethod
    def _frequencies(cls, text: str) -> dict[str, float]:
        words = cls._content_words(text)
        if not words:
            return {}

        counts: dict[str, int] = {}
        for word in words:
            counts[word] = counts.get(word, 0) + 1

        highest = max(counts.values())
        return {word: count / highest for word, count in counts.items()}

    @classmethod
    def _similarity(cls, left: str, right: str) -> float:
        a = set(cls._content_words(left))
        b = set(cls._content_words(right))
        if not a or not b:
            return 0.0

        jaccard = len(a & b) / max(len(a | b), 1)
        sequence = SequenceMatcher(None, left.lower(), right.lower()).ratio()
        return max(jaccard, sequence)

    @staticmethod
    def _polish_sentence(sentence: str) -> str:
        sentence = _WS_RE.sub(" ", sentence).strip()

        leadins = (
            r"^(?:yes|no|now|well|okay|ok)[,;:]?\s+",
            r"^(?:but\s+)?i think(?: one thing)?(?: we can all agree on)?[,;:]?\s*",
            r"^(?:and\s+)?what(?:'s| is) important is[,;:]?\s*",
            r"^(?:so\s+)?the point is[,;:]?\s*",
            r"^(?:now\s+)?our story concerns[,;:]?\s*",
        )
        for pattern in leadins:
            cleaned = re.sub(pattern, "", sentence, flags=re.IGNORECASE)
            if cleaned != sentence and len(cleaned) >= 40:
                sentence = cleaned
                break

        if sentence:
            sentence = sentence[0].upper() + sentence[1:]

        return sentence

    def summarize(self, text: str, *, title: str = "") -> str:
        sentences = split_sentences(text)

        # Drop weak/rhetorical caption fragments before scoring.
        sentences = [
            s.strip()
            for s in sentences
            if len(s.strip()) >= 55
            and len(s.strip()) <= 360
            and len(self._content_words(s)) >= 6
            and not s.strip().lower().startswith(
                (
                    "and ", "but ", "so ", "because ", "well ", "okay ", "ok ",
                    "yeah ", "i think ", "i believe ", "in my opinion ",
                    "you know ", "let's ", "we ", "our ", "i ", "i'm ", "i've ",
                )
            )
            and not s.rstrip().endswith("?")
            and not any(
                phrase in s.lower()
                for phrase in (
                    "we can all agree",
                    "our story concerns",
                    "what we're going to",
                    "i'm going to show",
                    "as you can see",
                    "the point i'm trying",
                    "we don't know",
                    "we do know",
                    "i don't know",
                    "i do know",
                    "he quotes",
                    "she quotes",
                    "i quote",
                    "there is one",
                    "there's one",
                )
            )
        ]

        if not sentences:
            return text[: self.max_chars].strip()

        frequencies = self._frequencies(text)
        title_words = set(self._content_words(title))
        total = max(len(sentences), 1)

        candidates: list[tuple[float, int, str]] = []

        for index, sentence in enumerate(sentences):
            words = self._content_words(sentence)
            if not words:
                continue

            lexical = sum(frequencies.get(w, 0.0) for w in words)
            lexical /= math.sqrt(max(len(words), 1))

            title_overlap = sum(1 for w in words if w in title_words)
            position_bonus = 0.20 * (1.0 - (index / total))

            # Penalize obvious intro/channel boilerplate and favor details.
            lowered = sentence.lower()
            boilerplate_penalty = 0.0
            for phrase in (
                "subscribe",
                "like and subscribe",
                "welcome back",
                "in today's video",
                "sponsor",
                "patreon",
                "thanks for watching",
                "click the link",
            ):
                if phrase in lowered:
                    boilerplate_penalty += 0.6

            detail_bonus = 0.0
            if re.search(r"\b\d+(?:\.\d+)?%?\b", sentence):
                detail_bonus += 0.18
            if re.search(r"\b(?:19|20)\d{2}\b", sentence):
                detail_bonus += 0.12

            proper_nouns = re.findall(r"\b[A-Z][a-z]{2,}\b", sentence)
            detail_bonus += min(len(proper_nouns), 4) * 0.035

            for term in (
                "according to",
                "located",
                "population",
                "controlled by",
                "operated by",
                "ministry",
                "government",
                "authority",
                "checkpoint",
                "border",
                "law",
                "percent",
                "million",
                "billion",
            ):
                if term in lowered:
                    detail_bonus += 0.08

            pronoun_penalty = 0.0
            pronoun_hits = len(
                re.findall(
                    r"\b(?:he|she|they|them|this|that|these|those|it|its)\b",
                    lowered,
                )
            )
            if pronoun_hits >= 3:
                pronoun_penalty = min(0.30, pronoun_hits * 0.05)

            if lowered.startswith(("there is ", "there are ", "there's ")):
                pronoun_penalty += 0.18

            score = (
                lexical
                + (title_overlap * 0.20)
                + position_bonus
                + min(detail_bonus, 0.45)
                - boilerplate_penalty
                - pronoun_penalty
            )
            candidates.append((score, index, sentence))

        selected: list[tuple[int, str]] = []

        for _, index, sentence in sorted(candidates, reverse=True):
            if any(self._similarity(sentence, other) >= 0.48 for _, other in selected):
                continue

            selected.append((index, sentence))
            if len(selected) >= self.max_sentences:
                break

        if not selected:
            selected = list(enumerate(sentences[: self.max_sentences]))

        # Preserve transcript chronology after scoring.
        selected.sort(key=lambda item: item[0])

        bullets: list[str] = []
        for _, sentence in selected:
            sentence = self._polish_sentence(sentence)
            if not sentence:
                continue
            if len(sentence) > 260:
                sentence = sentence[:260].rsplit(" ", 1)[0].rstrip() + "…"
            elif sentence[-1] not in ".!?":
                sentence += "."
            bullets.append(f"• {sentence}")

        summary = "\n".join(bullets)

        if len(summary) > self.max_chars:
            summary = summary[: self.max_chars].rsplit(" ", 1)[0].rstrip() + "…"

        return summary.strip()

def summarize_chunked(
    transcript: str,
    *,
    title: str,
    summarizer: Summarizer,
) -> str:
    chunks = chunk_transcript(transcript)

    if len(chunks) <= 1:
        return summarizer.summarize(transcript, title=title)

    chunk_summaries = [
        summarizer.summarize(chunk, title=title)
        for chunk in chunks
    ]

    # Strip bullet markers before the second-pass selector.
    combined = " ".join(
        line.lstrip("• ").strip()
        for summary in chunk_summaries
        for line in summary.splitlines()
        if line.strip()
    )
    return summarizer.summarize(combined, title=title)


def extract_transcript(
    url: str,
    *,
    cookie_file: str | Path | None = None,
) -> tuple[dict, CaptionTrack, str]:
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    cookie_path = Path(cookie_file).expanduser() if cookie_file else None
    if cookie_path and cookie_path.is_file():
        options["cookiefile"] = str(cookie_path)

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise SynopsisError(f"Could not inspect video captions: {exc}") from exc

    if not isinstance(info, dict):
        raise SynopsisError("yt-dlp returned no usable video information.")

    track = choose_caption_track(info)
    raw = _download_text(track.url)
    transcript = clean_caption_text(raw, track.ext)

    return info, track, transcript


def _format_duration(seconds: int | None) -> str:
    if not seconds:
        return "unknown"

    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def build_synopsis_for_url(
    url: str,
    *,
    cookie_file: str | Path | None = None,
    summarizer: Summarizer | None = None,
) -> str:
    info, track, transcript = extract_transcript(
        url,
        cookie_file=cookie_file,
    )

    title = str(info.get("title") or "Untitled")
    uploader = str(
        info.get("uploader")
        or info.get("channel")
        or info.get("creator")
        or "Unknown"
    )
    duration = info.get("duration")

    backend = summarizer or ExtractiveSummarizer()
    synopsis = summarize_chunked(
        transcript,
        title=title,
        summarizer=backend,
    )

    result = SynopsisResult(
        title=title,
        uploader=uploader,
        duration=int(duration) if duration else None,
        language=track.language,
        caption_source=track.source,
        transcript_chars=len(transcript),
        transcript_words=len(_WORD_RE.findall(transcript)),
        synopsis=synopsis,
    )

    caption_note = ""
    if result.caption_source == "automatic":
        caption_note = (
            "\nCaption note: automatic captions can mishear names, numbers, "
            "and specialized terms."
        )

    output = (
        f"📝 Synopsis\n\n"
        f"{result.title}\n"
        f"Source: {result.uploader}\n"
        f"Duration: {_format_duration(result.duration)}\n"
        f"Captions: {result.language} ({result.caption_source})\n"
        f"Transcript: {result.transcript_words:,} words"
        f"{caption_note}\n\n"
        f"Key points from the video:\n{result.synopsis}"
    )

    # Telegram text messages cap at 4096 characters. Leave room for edits and
    # avoid producing a transcript-sized wall of text.
    if len(output) > 3900:
        output = output[:3895].rsplit(" ", 1)[0].rstrip() + "…"

    return output
