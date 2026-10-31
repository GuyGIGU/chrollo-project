"""The alpha reader: a chart in, one record out.

Stage by stage, in the order the reader reads: ``chart`` (the frame and the daily range), ``line`` (the
swing line), ``box/`` (the walk: which pair of lines is the box, and its life), ``lps`` (the last pullback and
its trigger), ``story`` (the words), ``grade`` (the letter and the traits), ``state`` (the state word);
``reader.read`` runs them into one ``record.Read``. ``gate`` is the one way in for every caller, ``result``
and ``archive`` are what the reader hands out, ``stock`` is the stock's own facts, ``numbers`` every number the
reader reads and ``stamp`` the engine config version. A leaf: it imports nothing from the pipeline, the
webapp or the tools; ``config.settings`` is its one outward read.
"""
