# Don't trust me with cryptography.

"""
Implementation of https://gist.github.com/RubenSomsen/be7a4760dd4596d06963d67baf140406

Bob (Mint):
A = a*G
return A

Alice (Client):
Y = hash_to_curve(secret_message)
r = random blinding factor
B'= Y + r*G
return B'

Bob:
C' = a*B'
  (= a*Y + a*r*G)
return C'

Alice:
C = C' - r*A
 (= C' - a*r*G)
 (= a*Y)
return C, secret_message

Bob:
Y = hash_to_curve(secret_message)
C == a*Y
If true, C must have originated from Bob
"""

import hashlib

from secp256k1 import PrivateKey, PublicKey


def hash_to_curve(message: bytes):
    """Generates a point from the message hash and checks if the point lies on the curve.
    If it does not, it tries computing a new point from the hash."""
    point = None
    msg_to_hash = message
    while point is None:
        try:
            _hash = hashlib.sha256(msg_to_hash).digest()
            point = PublicKey(b"\x02" + _hash, raw=True)
        except:
            msg_to_hash = _hash
    return point


def step1_alice(secret_msg: str, blinding_factor: bytes = None):
    Y = hash_to_curve(secret_msg.encode("utf-8"))
    if blinding_factor:
        r = PrivateKey(privkey=blinding_factor, raw=True)
    else:
        r = PrivateKey()
    B_ = Y + r.pubkey
    return B_, r


def step2_bob(B_, a):
    C_ = B_.mult(a)
    return C_


def step3_alice(C_, r, A):
    C = C_ - A.mult(r)
    return C


def verify(a, C, secret_msg):
    Y = hash_to_curve(secret_msg.encode("utf-8"))
    return C == Y.mult(a)


### Below is a test of a simple positive and negative case

# # Alice's keys
# a = PrivateKey()
# A = a.pubkey
# secret_msg = "test"
# B_, r = step1_alice(secret_msg)
# C_ = step2_bob(B_, a)
# C = step3_alice(C_, r, A)
# print("C:{}, secret_msg:{}".format(C, secret_msg))
# assert verify(a, C, secret_msg)
# assert verify(a, C + C, secret_msg) == False  # adding C twice shouldn't pass
# assert verify(a, A, secret_msg) == False  # A shouldn't pass

# # Test operations
# b = PrivateKey()
# B = b.pubkey
# assert -A -A + A == -A  # neg
# assert B.mult(a) == A.mult(b)  # a*B = A*b
