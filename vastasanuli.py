import argparse
import dataclasses
import os
import random
import time
from collections import defaultdict
from functools import lru_cache
from typing import Iterable, List, Set

from playwright.sync_api import Page, sync_playwright

LETTER_COUNT_CHOICES = (5, 6)

screencast_mode = bool(os.environ.get("SCREENCAST"))

sanuli_letters = set("abcdefghijklmnopqrstuvwxyzåäö")
fi_freq = {
    l: i for i, l in enumerate("aitneslokuämvrjhypdögbfcwåq")
}  # https://jkorpela.fi/kielikello/kirjtil.html

with open("words.txt", encoding="utf-8") as wl_file:
    all_words = [
        w.strip().lower()
        for w in wl_file
        if len(w.strip()) in LETTER_COUNT_CHOICES and set(w.strip()) <= sanuli_letters
    ]


class Win(Exception):
    pass


class Loss(Exception):
    pass


class NoWords(Exception):
    pass


@dataclasses.dataclass
class Cell:
    content: str
    classes: Set[str]

    @property
    def empty(self) -> bool:
        return not self.content

    @property
    def correct(self) -> bool:
        return "correct" in self.classes

    @property
    def present(self) -> bool:
        return "present" in self.classes

    @property
    def absent(self) -> bool:
        return "absent" in self.classes


def get_rows(page: Page, *, n_letters: int) -> List[List[Cell]]:
    return [
        [
            Cell(
                content=cell.text_content().strip().lower(),
                classes=set(cell.get_property("className").json_value().split()),
            )
            for cell in row.query_selector_all(".tile")
        ]
        for row in page.query_selector_all(f".row-{n_letters}")
    ]


def enter_word(page: Page, word: str) -> bool:
    print(f"Entering word {word}")
    for letter in word:
        page.click(f'.keyboard-button:has-text("{letter.upper()}")')
        # time.sleep(.1)
    page.click("text=ARVAA")
    # time.sleep(.1)
    if page.is_visible("text=Ei sanulistalla"):
        return False  # invalid guess
    return True


def clear_entry(page: Page, *, n_letters: int) -> None:
    for x in range(n_letters):
        page.click('.keyboard-button:has-text("⌫")')


def new_game(page: Page) -> None:
    page.click("text=UUSI")


def check_win_state(page: Page) -> None:
    if page.query_selector_all("text=SANA OLI"):
        raise Loss()
    if page.query_selector_all("text=LÖYSIT"):
        raise Win()


def choose_game(page: Page, *, n_letters: int, waterfall=False) -> None:
    page.click("text=≡")
    time.sleep(.5)
    page.click(f"text={n_letters} MERKKIÄ")
    page.click("text=≡")
    time.sleep(.5)
    page.click(f"text={'KYLLÄ' if waterfall else 'EI'}")


def infer_next_options(rows: List[List[Cell]], *, n_letters: int) -> Iterable[str]:
    known_indexes = {}
    present_letters = set()
    forbidden_letters = set()
    known_unindexes = defaultdict(set)

    for y, row in enumerate(rows):
        if all(c.empty for c in row):
            continue
        for x, cell in enumerate(row):
            if not cell.content:
                continue
            if cell.correct:
                known_indexes[x] = cell.content
            elif cell.present:
                present_letters.add(cell.content)
            elif cell.absent:
                forbidden_letters.add(cell.content)
                known_unindexes[x].add(cell.content)

    # remove known good values from forbidden letters
    forbidden_letters -= set(known_indexes.values())
    forbidden_letters -= present_letters

    if len(known_indexes) == n_letters:
        raise Win("".join(c for (i, c) in sorted(known_indexes.items())))

    print(f"{forbidden_letters=}")
    print(f"{known_indexes=}")
    print(f"{known_unindexes=}")
    print(f"{present_letters=}")

    for word in all_words:
        if len(word) != n_letters:
            continue

        if known_indexes and not all(word[i] == l for i, l in known_indexes.items()):
            continue
        if known_unindexes and any(word[i] in ls for i, ls in known_unindexes.items()):
            continue
        wset = set(word)
        if wset & forbidden_letters:  # has some forbidden letters
            continue
        if present_letters - wset:  # missing some known present letters
            continue
        yield word


@lru_cache()
def score_word(word: str) -> float:
    freq_sum = 1.0 / sum(1 + fi_freq.get(letter, 0) for letter in word)
    entropy = len(set(word))
    return freq_sum * entropy


@lru_cache()
def get_start_words(n: int):
    return sorted(w for w in all_words if len(set(w)) == n)


def play(page: Page, *, n_letters: int) -> None:
    words_attempted = set()
    while True:
        print("Getting rows...")
        rows = get_rows(page, n_letters=n_letters)
        if not rows:  # may still be loading
            continue

        weights = None

        if all(c.empty for c in rows[0]):  # empty first row, so pick a start word
            word_cands = get_start_words(n_letters)
        else:
            word_cands = list(
                set(infer_next_options(rows, n_letters=n_letters)) - words_attempted
            )
            weights = [score_word(word) for word in word_cands]

        check_win_state(page)

        if not word_cands:
            print("No word candidates - trying random words instead...")
            word_cands = [w for w in all_words if len(w) == n_letters]
            weights = None

        print(f"{len(word_cands)} word candidates, attempted: {words_attempted}")

        while True:
            word = random.choices(word_cands, weights=weights)[0]
            # This isn't 100% bullet proof since word_choices is only updated
            # with words_attempted above, not here.
            words_attempted.add(word)
            if enter_word(page, word):
                break
            clear_entry(page, n_letters=n_letters)


def countdown(n=3):
    for x in range(n, 0, -1):
        print(x, end=" ")
        time.sleep(1)
    print("!")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-letters", "-n", type=int, default=5)
    ap.add_argument("--waterfall", default=False, action="store_true")
    args = ap.parse_args()
    n_letters = args.n_lettes
    waterfall = bool(args.waterfall)
    assert n_letters in LETTER_COUNT_CHOICES
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False)

        page = browser.new_page()
        page.goto("https://sanuli.fi/")
        page.wait_for_load_state("load")

        choose_game(page, n_letters=n_letters, waterfall=waterfall)

        if screencast_mode:
            countdown()

        while True:
            try:
                play(page, n_letters=n_letters)
            except (Win, Loss) as ex:
                print(f"---> {ex!r}")
            except KeyboardInterrupt:
                break
            time.sleep(0.75)
            new_game(page)
            time.sleep(0.75)
            continue


if __name__ == "__main__":
    main()
