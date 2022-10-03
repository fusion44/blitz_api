## Specializations
Some platforms implement special features on top of the main lightning implementation. This is the place to keep the code for these specializations.

Example:
RaspiBlitz implements a specialization for Core Lightning to unlock the wallet.

> ℹ️ This keeps dependencies as lean as possible for the main implementations. RaspiBlitz Core Lightning unlock specialization has a redis dependency but the main implementation does not.
