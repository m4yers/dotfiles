" Vim syntax file
" Language:     Helium
" Maintainer:   Artyom Goncharov <me@mayerscraft.com>
" Last Change:  December 24, 2015

if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif

" Syntax definitions {{{1
" Basic keywords {{{2
syn keyword   heliumConditional match if else
syn keyword   heliumOperator    as

syn match     heliumAssert      "\<assert\(\w\)*!" contained
syn match     heliumPanic       "\<panic\(\w\)*!" contained
syn keyword   heliumKeyword     break
syn keyword   heliumKeyword     box nextgroup=heliumBoxPlacement skipwhite skipempty
syn keyword   heliumKeyword     continue
syn keyword   heliumKeyword     fn nextgroup=heliumFuncName skipwhite skipempty
syn keyword   heliumKeyword     asm while for in if let def ret nil enum const statis
syn keyword   heliumStorage     move mut ref static const

syn match     heliumIdentifier  contains=heliumIdentifierPrime "\%([^[:cntrl:][:space:][:punct:][:digit:]]\|_\)\%([^[:cntrl:][:punct:][:space:]]\|_\)*" display contained
syn match     heliumFuncName    "\%([^[:cntrl:][:space:][:punct:][:digit:]]\|_\)\%([^[:cntrl:][:punct:][:space:]]\|_\)*" display contained

syn region    heliumBoxPlacement matchgroup=heliumBoxPlacementParens start="(" end=")" contains=TOP contained
" Ideally we'd have syntax rules set up to match arbitrary expressions. Since
" we don't, we'll just define temporary contained rules to handle balancing
" delimiters.
syn region    heliumBoxPlacementBalance start="(" end=")" containedin=heliumBoxPlacement transparent
syn region    heliumBoxPlacementBalance start="\[" end="\]" containedin=heliumBoxPlacement transparent
" {} are handled by heliumFoldBraces

syn region heliumMacroRepeat matchgroup=heliumMacroRepeatDelimiters start="$(" end=")" contains=TOP nextgroup=heliumMacroRepeatCount
syn match heliumMacroRepeatCount ".\?[*+]" contained
syn match heliumMacroVariable "$\w\+"

" Reserved (but not yet used) keywords {{{2
syn keyword   heliumReservedKeyword alignof become do offsetof priv pure sizeof typeof unsized yield abstract virtual final override macro

" Built-in types {{{2
syn keyword   heliumType        int string bool

" Things from the libstd v1 prelude (src/libstd/prelude/v1.rs) {{{2
" This section is just straight transformation of the contents of the prelude,
" to make it easy to update.

" Reexported core operators {{{3
syn keyword   heliumTrait       Copy Send Sized Sync
syn keyword   heliumTrait       Drop Fn FnMut FnOnce

" Reexported functions {{{3
" There’s no point in highlighting these; when one writes drop( or drop::< it
" gets the same highlighting anyway, and if someone writes `let drop = …;` we
" don’t really want *that* drop to be highlighted.
"syn keyword heliumFunction drop

" Reexported types and traits {{{3
syn keyword heliumTrait Box
syn keyword heliumTrait ToOwned
syn keyword heliumTrait Clone
syn keyword heliumTrait PartialEq PartialOrd Eq Ord
syn keyword heliumTrait AsRef AsMut Into From
syn keyword heliumTrait Default
syn keyword heliumTrait Iterator Extend IntoIterator
syn keyword heliumTrait DoubleEndedIterator ExactSizeIterator
syn keyword heliumEnum Option
syn keyword heliumEnumVariant Some None
syn keyword heliumEnum Result
syn keyword heliumEnumVariant Ok Err
syn keyword heliumTrait SliceConcatExt
syn keyword heliumTrait String ToString
syn keyword heliumTrait Vec

" Other syntax {{{2
syn keyword   heliumSelf        self
syn keyword   heliumBoolean     true false

syn match     heliumFuncCall    "\w\(\w\)*("he=e-1,me=e-1
syn match     heliumFuncCall    "\w\(\w\)*::<"he=e-3,me=e-3 " foo::<T>();

" This is merely a convention; note also the use of [A-Z], restricting it to
" latin identifiers rather than the full Unicode uppercase. I have not used
" [:upper:] as it depends upon 'noignorecase'
"syn match     heliumCapsIdent    display "[A-Z]\w\(\w\)*"

syn match     heliumOperator     display "\%(+\|-\|/\|*\|=\|\^\|&\||\|!\|>\|<\|<>\|%\)=\?"
" This one isn't *quite* right, as we could have binary-& with a reference
syn match     heliumSigil        display /&\s\+[&~@*][^)= \t\r\n]/he=e-1,me=e-1
syn match     heliumSigil        display /[&~@*][^)= \t\r\n]/he=e-1,me=e-1
" This isn't actually correct; a closure with no arguments can be `|| { }`.
" Last, because the & in && isn't a sigil
syn match     heliumOperator     display "&&\|||"
" This is heliumScopeCharacter rather than heliumArrow for the sake of matchparen,
" so it skips the ->; see http://stackoverflow.com/a/30309949 for details.
syn match     heliumScopeCharacter display ":"

syn match     heliumMacro       '\w\(\w\)*!' contains=heliumAssert,heliumPanic
syn match     heliumMacro       '#\w\(\w\)*' contains=heliumAssert,heliumPanic

syn match     heliumEscapeError   display contained /\\./
syn match     heliumEscape        display contained /\\\([nrt0\\'"]\|x\x\{2}\)/
syn match     heliumEscapeUnicode display contained /\\\(u\x\{4}\|U\x\{8}\)/
syn match     heliumEscapeUnicode display contained /\\u{\x\{1,6}}/
syn match     heliumStringContinuation display contained /\\\n\s*/
syn region    heliumString      start=+b"+ skip=+\\\\\|\\"+ end=+"+ contains=heliumEscape,heliumEscapeError,heliumStringContinuation
syn region    heliumString      start=+"+ skip=+\\\\\|\\"+ end=+"+ contains=heliumEscape,heliumEscapeUnicode,heliumEscapeError,heliumStringContinuation,@Spell
syn region    heliumString      start='b\?r\z(#*\)"' end='"\z1' contains=@Spell

syn region    heliumAttribute   start="#!\?\[" end="\]" contains=heliumString,heliumDerive
syn region    heliumDerive      start="derive(" end=")" contained contains=heliumDeriveTrait
" This list comes from src/libsyntax/ext/deriving/mod.rs
" Some are deprecated (Encodable, Decodable) or to be removed after a new snapshot (Show).
syn keyword   heliumDeriveTrait contained Clone Hash heliumcEncodable heliumcDecodable Encodable Decodable PartialEq Eq PartialOrd Ord Rand Show Debug Default FromPrimitive Send Sync Copy

" Number literals
syn match     heliumDecNumber   display "\<[0-9][0-9_]*\%([iu]\%(size\|8\|16\|32\|64\)\)\="
syn match     heliumHexNumber   display "\<0x[a-fA-F0-9_]\+\%([iu]\%(size\|8\|16\|32\|64\)\)\="
syn match     heliumOctNumber   display "\<0o[0-7_]\+\%([iu]\%(size\|8\|16\|32\|64\)\)\="
syn match     heliumBinNumber   display "\<0b[01_]\+\%([iu]\%(size\|8\|16\|32\|64\)\)\="

" Special case for numbers of the form "1." which are float literals, unless followed by
" an identifier, which makes them integer literals with a method call or field access,
" or by another ".", which makes them integer literals followed by the ".." token.
" (This must go first so the others take precedence.)
syn match     heliumFloat       display "\<[0-9][0-9_]*\.\%([^[:cntrl:][:space:][:punct:][:digit:]]\|_\|\.\)\@!"
" To mark a number as a normal float, it must have at least one of the three things integral values don't have:
" a decimal point and more numbers; an exponent; and a type suffix.
syn match     heliumFloat       display "\<[0-9][0-9_]*\%(\.[0-9][0-9_]*\)\%([eE][+-]\=[0-9_]\+\)\=\(f32\|f64\)\="
syn match     heliumFloat       display "\<[0-9][0-9_]*\%(\.[0-9][0-9_]*\)\=\%([eE][+-]\=[0-9_]\+\)\(f32\|f64\)\="
syn match     heliumFloat       display "\<[0-9][0-9_]*\%(\.[0-9][0-9_]*\)\=\%([eE][+-]\=[0-9_]\+\)\=\(f32\|f64\)"

" For the benefit of delimitMate
syn region heliumLifetimeCandidate display start=/&'\%(\([^'\\]\|\\\(['nrt0\\\"]\|x\x\{2}\|u\x\{4}\|U\x\{8}\)\)'\)\@!/ end=/[[:cntrl:][:space:][:punct:]]\@=\|$/ contains=heliumSigil,heliumLifetime
syn region heliumGenericRegion display start=/<\%('\|[^[cntrl:][:space:][:punct:]]\)\@=')\S\@=/ end=/>/ contains=heliumGenericLifetimeCandidate
syn region heliumGenericLifetimeCandidate display start=/\%(<\|,\s*\)\@<='/ end=/[[:cntrl:][:space:][:punct:]]\@=\|$/ contains=heliumSigil,heliumLifetime

"heliumLifetime must appear before heliumCharacter, or chars will get the lifetime highlighting
syn match     heliumLifetime    display "\'\%([^[:cntrl:][:space:][:punct:][:digit:]]\|_\)\%([^[:cntrl:][:punct:][:space:]]\|_\)*"
syn match   heliumCharacterInvalid   display contained /b\?'\zs[\n\r\t']\ze'/
" The groups negated here add up to 0-255 but nothing else (they do not seem to go beyond ASCII).
syn match   heliumCharacterInvalidUnicode   display contained /b'\zs[^[:cntrl:][:graph:][:alnum:][:space:]]\ze'/
syn match   heliumCharacter   /b'\([^\\]\|\\\(.\|x\x\{2}\)\)'/ contains=heliumEscape,heliumEscapeError,heliumCharacterInvalid,heliumCharacterInvalidUnicode
syn match   heliumCharacter   /'\([^\\]\|\\\(.\|x\x\{2}\|u\x\{4}\|U\x\{8}\|u{\x\{1,6}}\)\)'/ contains=heliumEscape,heliumEscapeUnicode,heliumEscapeError,heliumCharacterInvalid

syn match heliumShebang /\%^#![^[].*/
syn region heliumCommentLine                                        start="//"                      end="$"   contains=heliumTodo,@Spell
syn region heliumCommentLineDoc                                     start="//\%(//\@!\|!\)"         end="$"   contains=heliumTodo,@Spell
syn region heliumCommentBlock    matchgroup=heliumCommentBlock        start="/\*\%(!\|\*[*/]\@!\)\@!" end="\*/" contains=heliumTodo,heliumCommentBlockNest,@Spell
syn region heliumCommentBlockDoc matchgroup=heliumCommentBlockDoc     start="/\*\%(!\|\*[*/]\@!\)"    end="\*/" contains=heliumTodo,heliumCommentBlockDocNest,@Spell
syn region heliumCommentBlockNest matchgroup=heliumCommentBlock       start="/\*"                     end="\*/" contains=heliumTodo,heliumCommentBlockNest,@Spell contained transparent
syn region heliumCommentBlockDocNest matchgroup=heliumCommentBlockDoc start="/\*"                     end="\*/" contains=heliumTodo,heliumCommentBlockDocNest,@Spell contained transparent
" FIXME: this is a really ugly and not fully correct implementation. Most
" importantly, a case like ``/* */*`` should have the final ``*`` not being in
" a comment, but in practice at present it leaves comments open two levels
" deep. But as long as you stay away from that particular case, I *believe*
" the highlighting is correct. Due to the way Vim's syntax engine works
" (greedy for start matches, unlike helium's tokeniser which is searching for
" the earliest-starting match, start or end), I believe this cannot be solved.
" Oh you who would fix it, don't bother with things like duplicating the Block
" rules and putting ``\*\@<!`` at the start of them; it makes it worse, as
" then you must deal with cases like ``/*/**/*/``. And don't try making it
" worse with ``\%(/\@<!\*\)\@<!``, either...

syn keyword heliumTodo contained TODO FIXME SHIT HMM ERROR XXX NB NOTE

" Folding rules {{{2
" Trivial folding rules to begin with.
" FIXME: use the AST to make really good folding
syn region heliumFoldBraces start="{" end="}" transparent fold

" Default highlighting {{{1
hi def link heliumDecNumber       heliumNumber
hi def link heliumHexNumber       heliumNumber
hi def link heliumOctNumber       heliumNumber
hi def link heliumBinNumber       heliumNumber
hi def link heliumIdentifierPrime heliumIdentifier
hi def link heliumTrait           heliumType
hi def link heliumDeriveTrait     heliumTrait

hi def link heliumMacroRepeatCount   heliumMacroRepeatDelimiters
hi def link heliumMacroRepeatDelimiters   Macro
hi def link heliumMacroVariable Define
hi def link heliumSigil         StorageClass
hi def link heliumEscape        Special
hi def link heliumEscapeUnicode heliumEscape
hi def link heliumEscapeError   Error
hi def link heliumStringContinuation Special
hi def link heliumString        String
hi def link heliumCharacterInvalid Error
hi def link heliumCharacterInvalidUnicode heliumCharacterInvalid
hi def link heliumCharacter     Character
hi def link heliumNumber        Number
hi def link heliumBoolean       Boolean
hi def link heliumEnum          heliumType
hi def link heliumEnumVariant   heliumConstant
hi def link heliumConstant      Constant
hi def link heliumSelf          Constant
hi def link heliumFloat         Float
hi def link heliumScopeCharacter heliumOperator
hi def link heliumOperator      Operator
hi def link heliumKeyword       Keyword
hi def link heliumReservedKeyword Error
hi def link heliumConditional   Conditional
hi def link heliumIdentifier    Identifier
hi def link heliumCapsIdent     heliumIdentifier
hi def link heliumFunction      Function
hi def link heliumFuncName      Function
hi def link heliumFuncCall      Function
hi def link heliumShebang       Comment
hi def link heliumCommentLine   Comment
hi def link heliumCommentLineDoc SpecialComment
hi def link heliumCommentBlock  heliumCommentLine
hi def link heliumCommentBlockDoc heliumCommentLineDoc
hi def link heliumAssert        PreCondit
hi def link heliumPanic         PreCondit
hi def link heliumMacro         Macro
hi def link heliumType          Type
hi def link heliumTodo          Todo
hi def link heliumAttribute     PreProc
hi def link heliumDerive        PreProc
hi def link heliumStorage       StorageClass
hi def link heliumObsoleteStorage Error
hi def link heliumLifetime      Special
hi def link heliumInvalidBareKeyword Error
hi def link heliumExternCrate   heliumKeyword
hi def link heliumBoxPlacementParens Delimiter

" Other Suggestions:
" hi heliumAttribute ctermfg=cyan
" hi heliumDerive ctermfg=cyan
" hi heliumAssert ctermfg=yellow
" hi heliumPanic ctermfg=red
" hi heliumMacro ctermfg=magenta

syn sync minlines=200
syn sync maxlines=500

let b:current_syntax = "helium"
