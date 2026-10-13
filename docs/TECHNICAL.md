# How the engine works

A Viper CF image contains a compressed PowerPC program and a descriptor stating the uncompressed and compressed lengths, load address and original compressed-stream checksum.

Sapera reads the user's own media, finds the descriptor, expands the ZIN token stream and identifies the resulting executable by SHA-256. Every proposed change is checked against an exact original instruction word. Unknown hashes never get guessed at.

The primary rewriting backend treats the existing decompression behavior as a constraint. It changes literals or reconstructs match references, locally retokenizes where necessary, and balances equivalent encoded values so that the **compressed byte count and original 32-bit additive checksum** stay unchanged. The candidate is expanded again and checked byte-for-byte against the desired patched executable.

Some exact revision/profile combinations also have precomputed differences. Sapera only uses these when it checks the original compressed-stream SHA-256, original executable SHA-256 **and** requested target executable SHA-256. Anything else has to go through the general rewriter.

That proves the file was rewritten consistently. It does **not** prove that the game can reach gameplay. A dead-RTC game can get past one validator and fail a second one, get stuck on empty backup data, or require missing cabinet I/O.

An earlier PowerPC bug was particularly nasty: taking a negative conditional branch (`bc`) and changing only its opcode to an unconditional `b` can change its signed displacement, sending it about 64 KiB forward. The included database validator detects that family of malformed replacements.

Do not remove the exact input fingerprint guard, original-word check, branch validator or final decompression assertions to make a failing patch appear usable.
