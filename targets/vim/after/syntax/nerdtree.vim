" Custom NERDTree file highlighting (hex colors)
" Uses matchadd() to overlay colors on top of syntax highlighting

hi NTShell guifg=#d86a5f
hi NTMd    guifg=#3074cf
hi NTCPPh  guifg=#83a598
hi NTCPPs  guifg=#458588
hi NTPy    guifg=#3db363
hi NTPyc   guifg=#3a3a3a
hi NTTxt   guifg=#665c54
hi NTTmp   guifg=#504945
hi NTMake  guifg=#fe8019
hi NTCMake guifg=#fe8019
hi NERDTreeExecFile guifg=NONE

" Clear old matches to allow re-sourcing
call clearmatches()

let s:tail = '\ze.\{-}$'

call matchadd('NTShell', '\c\zs[^ ].*\.sh' . s:tail)
call matchadd('NTMd',    '\c\zs[^ ].*\.md' . s:tail)
call matchadd('NTCPPh',  '\c\zs[^ ].*\.\(hpp\|hxx\|h\)' . s:tail)
call matchadd('NTCPPs',  '\c\zs[^ ].*\.\(cpp\|cxx\|c\)' . s:tail)
call matchadd('NTPy',    '\c\zs[^ ].*\.py' . s:tail)
call matchadd('NTPyc',   '\c\zs[^ ].*\.pyc' . s:tail)
call matchadd('NTTxt',   '\c\zs[^ ].*\.txt' . s:tail)
call matchadd('NTTmp',   '\c\zs[^ ].*\.tmp' . s:tail)
call matchadd('NTMake',  '\zsMakefile' . s:tail)
call matchadd('NTCMake', '\zsCMakeLists\.txt' . s:tail)
