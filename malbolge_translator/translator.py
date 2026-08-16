#!/usr/bin/env python3
"""
Main Malbolge Translator - Anchor-aware text to Malbolge translation.

Combines linear word chaining with periodic anchor resets for long texts.
Supports Unicode via lexicon transliteration.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from malbolge import (
    GenerationConfig,
    MalbolgeInterpreter,
    MalbolgeMachine,
    MalbolgeRuntimeError,
    ProgramGenerator,
)
from malbolge.encoding import reverse_normalize
from time import perf_counter_ns

from .lexicon import Lexicon, DEFAULT_LEXICON, transliterate
from .anchor import AnchorManager, AnchorState, WordBank, BankEntry
from .backend import MalbolgeBackend, get_backend


@dataclass
class WordResult:
    index: int
    word: str
    continuation: str
    anchor_name: str
    from_bank: bool
    success: bool = True
    error: Optional[str] = None


@dataclass
class TranslationResult:
    original_text: str
    processed_text: str
    words: List[WordResult]
    full_opcodes: str
    full_program: str  # ASCII Malbolge source
    stats: dict
    anchors_used: List[str]
    
    def save_all(self, output_dir: Path, base_name: str = "output") -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for i, w in enumerate(self.words):
            (output_dir / f"{base_name}_word_{i:04d}.op").write_text(w.continuation, encoding="utf-8")
            (output_dir / f"{base_name}_word_{i:04d}.json").write_text(
                json.dumps({
                    "index": w.index, "word": w.word, "opcodes": w.continuation,
                    "anchor": w.anchor_name, "from_bank": w.from_bank, "success": w.success
                }, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        
        (output_dir / f"{base_name}_full.op").write_text(self.full_opcodes, encoding="utf-8")
        (output_dir / f"{base_name}_full.mal").write_text(self.full_program, encoding="utf-8")
        (output_dir / f"{base_name}_manifest.json").write_text(json.dumps({
            "original": self.original_text, "processed": self.processed_text,
            "words": len(self.words), "anchors": self.anchors_used,
            "opcodes": len(self.full_opcodes), "stats": self.stats
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Saved to {output_dir}")


class MalbolgeTranslator:
    """
    Translates arbitrary text to pure Malbolge programs.
    
    Architecture:
    - Bootstrap to anchor state once at start
    - Chain words linearly (each continues from previous machine state)
    - Periodic anchor resets to prevent state drift
    - Optional word bank cache for words from anchor state
    - Unicode support via lexicon transliteration
    """
    
    def __init__(
        self,
        max_search_depth: int = 5,
        random_seed: int = 42,
        anchor_interval: int = 50,
        use_word_bank: bool = True,
        cache_dir: Optional[Path] = None,
        lexicon: Optional[Lexicon] = None,
    ):
        self.generator = ProgramGenerator()
        self.interpreter = MalbolgeInterpreter()
        self.max_search_depth = max_search_depth
        self.random_seed = random_seed
        self.cfg = GenerationConfig(
            opcode_choices="op*",
            max_search_depth=max_search_depth,
            random_seed=random_seed,
        )
        self.anchor_interval = anchor_interval
        self.use_bank = use_word_bank
        
        self.backend = get_backend(self.generator)
        
        cache_dir = cache_dir or Path.cwd() / ".malbolge_cache"
        self.anchors = AnchorManager(self.generator, self.interpreter, cache_dir)
        self.bank = WordBank(self.generator, self.interpreter, cache_dir)
        self.lexicon = lexicon or Lexicon()
        
        self.anchors.load()
        self.bank.load()
        self.anchors.default()
    
    def translate(
        self,
        text: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> TranslationResult:
        """Translate text to Malbolge opcodes."""
        # 1. Transliterate Unicode to ASCII
        processed = transliterate(text, self.lexicon)
        
        # 2. Split into words preserving spaces
        words = re.split(r'(\s+)', processed)
        words = [w for w in words if w]
        
        # 3. Generate with anchor resets
        return self._generate(words, progress_callback, processed, text)
    
    def _generate(
        self,
        words: list,
        progress_cb: Optional[Callable[[int, int, str], None]],
        processed: str,
        original: str,
    ) -> TranslationResult:
        results = []
        full_ops = ""
        anchors_used = []
        
        # Bootstrap to anchor
        anchor = self.anchors.default()
        machine = anchor.machine.copy()
        full_ops = anchor.bootstrap_opcodes
        anchors_used.append(anchor.name)
        
        total_evals = 0
        total_dur_ns = 0
        
        for i, word in enumerate(words):
            if progress_cb:
                progress_cb(i, len(words), word)
            print(f"[Word {i+1}/{len(words)}] '{word}' @{anchor.name}")
            
            # Anchor reset - clear word bank cache to prevent state drift
            # NOTE: We do NOT reset machine state or add bridge ops to full_ops.
            # Bridges are context-dependent and don't work when re-executed in the full program.
            # Instead, we clear the word bank cache periodically to prevent memory growth.
            if i > 0 and i % self.anchor_interval == 0:
                print(f"  [RESET] Clearing word bank cache at word {i}")
                self.bank.entries.clear()
                # Optionally: reset machine to anchor state for generation purposes
                # But we DON'T change the machine state for the final program
                # machine = anchor.machine.copy()
            
            # Word bank disabled - continuations are state-dependent in Malbolge
            # and can only be safely reused from exact anchor state
            from_bank = False
            cont = ""
            stats = {}
            
            if not from_bank:
                cont, machine, stats = self._gen_word(word, machine, full_ops, i == len(words)-1)
                if cont is None:
                    results.append(WordResult(i, word, "", anchor.name, False, False, stats.get("error")))
                    break
                
                # Cache if at anchor state
                if (self.use_bank and
                    machine.a == anchor.machine.a and
                    machine.c == anchor.machine.c and
                    machine.d == anchor.machine.d):
                    self.bank.entries[(anchor.hash, word)] = BankEntry(
                        word=word, anchor_hash=anchor.hash,
                        continuation=cont, stats=stats,
                    )
            
            results.append(WordResult(i, word, cont, anchor.name, from_bank))
            full_ops += cont
            total_evals += stats.get("evaluations", 0)
            total_dur_ns += stats.get("duration_ns", 0)
        
        full_program = "".join(reverse_normalize(full_ops))
        
        return TranslationResult(
            original_text=original,
            processed_text=processed,
            words=results,
            full_opcodes=full_ops,
            full_program=full_program,
            stats={
                "words": len(results),
                "evaluations": total_evals,
                "duration_s": total_dur_ns / 1e9,
                "anchors_used": len(set(anchors_used)),
            },
            anchors_used=anchors_used,
        )
    
    def _gen_word(
        self, word: str, start_m: MalbolgeMachine, prefix: str, final: bool
    ) -> Tuple[Optional[str], Optional[MalbolgeMachine], dict]:
        """Generate single word continuation from machine state using backend."""
        from time import perf_counter_ns
        
        start_ns = perf_counter_ns()
        
        # Use backend to search for continuation
        try:
            cont, machine, stats = self.backend.search_continuation(
                start_machine=start_m,
                target_text=word,
                max_search_depth=self.max_search_depth,
                random_seed=self.random_seed,
            )
            
            # If final, add halt
            if final:
                from malbolge import MalbolgeInterpreter
                interp = MalbolgeInterpreter()
                # Execute the continuation to get final state
                vr = interp.execute_from_snapshot(start_m, cont + "v", capture_machine=True)
                cont = cont + "v"
                machine = vr.machine
            else:
                # Execute to get machine state
                vr = self.interpreter.execute_from_snapshot(start_m, cont, capture_machine=True)
                machine = vr.machine
            
            dur = perf_counter_ns() - start_ns
            stats["duration_ns"] = dur
            
            return cont, machine, stats
            
        except MalbolgeRuntimeError as e:
            return None, None, {"error": str(e)}
    
    def execute(self, result: TranslationResult, max_steps: int = 5_000_000) -> str:
        """Execute the generated program and verify output against both processed and original text."""
        out = self.interpreter.execute(result.full_opcodes, max_steps=max_steps, capture_machine=True)
        processed_match = out.output == result.processed_text
        original_match = out.output == result.original_text
        print(f"Output: {repr(out.output)}")
        print(f"Steps: {out.steps}, Halt: {out.halt_reason}")
        print(f"Processed match: {processed_match}")
        print(f"Original match: {original_match}")
        if not processed_match and not original_match:
            print(f"Expected (processed): {repr(result.processed_text)}")
            print(f"Expected (original): {repr(result.original_text)}")
        return out.output
    
    def save_cache(self) -> None:
        self.anchors.save()
        self.bank.save()
        print("[Cache] Saved anchors and word bank")


# ============================================================
# COMMON WORD LISTS FOR PRE-POPULATION
# ============================================================

SPANISH_COMMON = [
    "el","la","de","que","y","en","un","a","se","no","te","lo","le","da","su","por","son","con","para","al",
    "del","los","las","una","uno","sus","les","me","mi","tu","es","ha","he","si","ya","va","ve","muy","más",
    "como","pero","sus","está","esta","esté","están","estás","estoy","somos","sois","son","era","eras","eran",
    "fue","fueron","será","serán","haber","había","hacer","hace","hecho","hacen","hacía","hagan","decir","dice",
    "dicho","dicen","dijo","decía","digan","ver","veo","visto","ven","vio","veía","verán","saber","sé","sabe",
    "sabes","sabemos","sabía","sabrán","querer","quiero","quiere","quería","quisiera","quieren","poder","puedo",
    "puede","puedes","podemos","podía","podrán","tener","tengo","tiene","tienes","tenemos","tenía","tendrán",
    "ir","voy","va","vas","vamos","iba","irán","fui","fue","venir","vengo","vienes","viene","venimos","venía",
    "vendrán","dar","doy","da","das","damos","daba","darán","di","dio","estar","estoy","estás","está","estamos",
    "estaba","estarán","llegar","llego","llega","llegas","llegamos","llegaba","llegarán","pasar","paso","pasa",
    "pasas","pasamos","pasaba","pasarán","deber","debo","debe","debes","debemos","debía","deberán","poner","pongo",
    "pone","pones","ponemos","ponía","pondrán","parecer","parezco","parece","pareces","parecemos","parecía",
    "parecerán","quedar","quedo","queda","quedas","quedamos","quedaba","quedarán","creer","creo","cree","crees",
    "creemos","creía","creerán","hablar","hablo","habla","hablas","hablamos","hablaba","hablarán","llevar","llevo",
    "lleva","llevas","llevamos","llevaba","llevarán","dejar","dejo","deja","dejas","dejamos","dejaba","dejarán",
    "seguir","sigo","sigue","sigues","seguimos","seguía","seguirán","encontrar","encuentro","encuentra",
    "encuentras","encontramos","encontraba","encontrarán","llamar","llamo","llama","llamas","llamamos","llamaba",
    "llamarán","venir","vengo","vienes","viene","venimos","venía","vendrán","pensar","pienso","piensa","piensas",
    "pensamos","pensaba","pensarán","salir","salgo","sale","sales","salimos","salía","saldrán","volver","vuelvo",
    "vuelve","vuelves","volvemos","volvía","volverán","tomar","tomo","toma","tomas","tomamos","tomaba","tomarán",
    "conocer","conozco","conoce","conoces","conocemos","conocía","conocerán","vivir","vivo","vive","vives",
    "vivimos","vivía","vivirán","sentir","siento","siente","sientes","sentimos","sentía","sentirán","tratar",
    "trato","trata","tratas","tratamos","trataba","tratarán","mirar","miro","mira","miras","miramos","miraba",
    "mirarán","contar","cuento","cuenta","cuentas","contamos","contaba","contarán","empezar","empiezo","empieza",
    "empiezas","empezamos","empezaba","empezarán","esperar","espero","espera","esperas","esperamos","esperaba",
    "esperarán","buscar","busco","busca","buscas","buscamos","buscaba","buscarán","existir","existo","existe",
    "existes","existimos","existía","existirán","entrar","entro","entra","entras","entramos","entraba","entrarán",
    "trabajar","trabajo","trabaja","trabajas","trabajamos","trabajaba","trabajarán","escribir","escribo","escribe",
    "escribes","escribimos","escribía","escribirán",
]

ENGLISH_COMMON = [
    "the","be","to","of","and","a","in","that","have","I","it","for","not","on","with","he","as","you","do","at",
    "this","but","his","by","from","they","we","say","her","she","or","an","will","my","one","all","would",
    "there","their","what","so","up","out","if","about","who","get","which","go","me","when","make","can","like",
    "time","no","just","him","know","take","people","into","year","your","good","some","could","them","see",
    "other","than","then","now","look","only","come","its","over","think","also","back","after","use","two",
    "how","our","work","first","well","way","even","new","want","because","any","these","give","day","most","us",
]

CODE_COMMON = [
    "def","class","import","from","return","if","else","elif","for","while","try","except","finally","with",
    "as","lambda","yield","async","await","True","False","None","self","super","init","str","int","float","bool",
    "list","dict","set","tuple","len","range","enumerate","zip","map","filter","print","input","open","read",
    "write","close","append","extend","pop","remove","fn","let","mut","const","struct","impl","trait","mod",
    "use","pub","match","loop","break","continue","move","ref","box","vec","string","option","result","ok",
    "err","some","none","unwrap","expect","panic","assert",
]