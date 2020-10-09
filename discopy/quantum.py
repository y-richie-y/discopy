# -*- coding: utf-8 -*-

"""
Implements classical-quantum maps and circuits.
"""

import random
import math
from itertools import takewhile

from discopy import messages, monoidal, rigid
from discopy.cat import AxiomError
from discopy.rigid import Ob, Ty, Diagram
from discopy.tensor import np, Dim, Tensor, TensorFunctor


def index2bitstring(i, length):
    """
    Turns an index into a bitstring of a given length.

    >>> index2bitstring(42, 8)
    (0, 0, 1, 0, 1, 0, 1, 0)
    """
    return tuple(map(int, '{{:0{}b}}'.format(length).format(i)))

def bitstring2index(bitstring):
    """
    Turns a bitstring into an index.

    >>> bitstring2index((0, 0, 1, 0, 1, 0, 1, 0))
    42
    """
    return sum(value * 2 ** i for i, value in enumerate(bitstring[::-1]))


class CQ(Ty):
    """
    Implements the dimensions of classical-quantum systems.

    Parameters
    ----------
    classical : :class:`discopy.tensor.Dim`
        Classical dimension.
    quantum : :class:`discopy.tensor.Dim`
        Quantum dimension.

    Note
    ----

    In the category of monoids, :class:`CQ` is the product of :class:`C` and
    :class:`Q`, which are both isomorphic to :class:`discopy.tensor.Dim`.

    Examples
    --------
    >>> CQ(Dim(2), Dim(2))
    C(Dim(2)) @ Q(Dim(2))
    >>> CQ(Dim(2), Dim(2)) @ CQ(Dim(2), Dim(2))
    C(Dim(2, 2)) @ Q(Dim(2, 2))
    """
    def __init__(self, classical=Dim(1), quantum=Dim(1)):
        self.classical, self.quantum = classical, quantum
        types = [Ob("C({})".format(dim)) for dim in classical]\
            + [Ob("Q({})".format(dim)) for dim in quantum]
        super().__init__(*types)

    def __repr__(self):
        if not self:
            return "CQ()"
        if not self.classical:
            return "Q({})".format(repr(self.quantum))
        if not self.quantum:
            return "C({})".format(repr(self.classical))
        return "C({}) @ Q({})".format(repr(self.classical), repr(self.quantum))

    def __str__(self):
        return repr(self)

    def tensor(self, other):
        return CQ(
            self.classical @ other.classical, self.quantum @ other.quantum)

    @property
    def l(self):
        return CQ(self.classical[::-1], self.quantum[::-1])

    @property
    def r(self):
        return self.l


class C(CQ):
    """
    Implements the classical dimension of a classical-quantum system,
    see :class:`CQ`.
    """
    def __init__(self, dim=Dim(1)):
        super().__init__(dim, Dim(1))


class Q(CQ):
    """
    Implements the quantum dimension of a classical-quantum system,
    see :class:`CQ`.
    """
    def __init__(self, dim=Dim(1)):
        super().__init__(Dim(1), dim)


class CQMap(rigid.Box):
    """
    Implements classical-quantum maps.

    Parameters
    ----------
    dom : :class:`CQ`
        Domain.
    cod : :class:`CQ`
        Codomain.
    array : list, optional
        Array of size :code:`product(data.dom @ data.cod)`.
    data : :class:`discopy.tensor.Tensor`, optional
        Tensor with domain :code:`dom.classical @ dom.quantum ** 2`
        and codomain :code:`cod.classical @ cod.quantum ** 2``.
    """
    def __init__(self, dom, cod, array=None, data=None):
        if array is None and data is None:
            raise ValueError("One of array or data must be given.")
        if data is None:
            data = Tensor(dom.classical @ dom.quantum @ dom.quantum,
                          cod.classical @ cod.quantum @ cod.quantum, array)
        self.array = data.array
        super().__init__("CQMap", dom, cod, data=data)

    def __eq__(self, other):
        return isinstance(other, CQMap)\
            and (self.dom, self.cod) == (other.dom, other.cod)\
            and self.data == other.data

    def __repr__(self):
        return "CQMap(dom={}, cod={}, array={})".format(
            self.dom, self.cod, np.array2string(self.array.flatten()))

    def __str__(self):
        return repr(self)

    def __add__(self, other):
        if (self.dom, self.cod) != (other.dom, other.cod):
            raise AxiomError(messages.cannot_add(self, other))
        return CQMap(self.dom, self.cod, self.array + other.array)

    @staticmethod
    def id(dom):
        data = Tensor.id(dom.classical @ dom.quantum @ dom.quantum)
        return CQMap(dom, dom, data.array)

    def then(self, *others):
        if len(others) != 1:
            return super().then(*others)
        data = self.data >> others[0].data
        return CQMap(self.dom, others[0].cod, data.array)

    def dagger(self):
        return CQMap(self.cod, self.dom, self.data.dagger().array)

    def tensor(self, *others):
        if len(others) != 1:
            return super().tensor(*others)
        f = rigid.Box('f', Ty('c00', 'q00', 'q00'), Ty('c10', 'q10', 'q10'))
        g = rigid.Box('g', Ty('c01', 'q01', 'q01'), Ty('c11', 'q11', 'q11'))
        ob = {Ty("{}{}{}".format(a, b, c)):
              z.__getattribute__(y).__getattribute__(x)
              for a, x in zip(['c', 'q'], ['classical', 'quantum'])
              for b, y in zip([0, 1], ['dom', 'cod'])
              for c, z in zip([0, 1], [self, others[0]])}
        ar = {f: self.array, g: others[0].array}
        permute_above = Diagram.id(f.dom[:1] @ g.dom[:1] @ f.dom[1:2])\
            @ Diagram.swap(g.dom[1:2], f.dom[2:]) @ Diagram.id(g.dom[2:])\
            >> Diagram.id(f.dom[:1]) @ Diagram.swap(g.dom[:1], f.dom[1:])\
            @ Diagram.id(g.dom[1:])
        permute_below =\
            Diagram.id(f.cod[:1]) @ Diagram.swap(f.cod[1:], g.cod[:1])\
            @ Diagram.id(g.cod[1:])\
            >> Diagram.id(f.cod[:1] @ g.cod[:1] @ f.cod[1:2])\
            @ Diagram.swap(f.cod[2:], g.cod[1:2]) @ Diagram.id(g.cod[2:])
        F = TensorFunctor(ob, ar)
        array = F(permute_above >> f @ g >> permute_below).array
        dom, cod = self.dom @ others[0].dom, self.cod @ others[0].cod
        return CQMap(dom, cod, array)

    @staticmethod
    def swap(left, right):
        data = Tensor.swap(left.classical, right.classical)\
            @ Tensor.swap(left.quantum, right.quantum)\
            @ Tensor.swap(left.quantum, right.quantum)
        return CQMap(left @ right, right @ left, data.array)

    @staticmethod
    def measure(dim, destructive=True):
        if not dim:
            return CQMap(CQ(), CQ(), np.array(1))
        if len(dim) == 1:
            if destructive:
                array = np.array([
                    int(i == j == k)
                    for i in range(dim[0])
                    for j in range(dim[0])
                    for k in range(dim[0])])
                return CQMap(Q(dim), C(dim), array)
            array = np.array([
                int(i == j == k == l == m)
                for i in range(dim[0])
                for j in range(dim[0])
                for k in range(dim[0])
                for l in range(dim[0])
                for m in range(dim[0])])
            return CQMap(Q(dim), C(dim) @ Q(dim), array)
        return CQMap.measure(dim[:1], destructive=destructive)\
            @ CQMap.measure(dim[1:], destructive=destructive)

    @staticmethod
    def encode(dim, constructive=True):
        return CQMap.measure(dim, destructive=constructive).dagger()

    @staticmethod
    def pure(tensor):
        return CQMap(Q(tensor.dom), Q(tensor.cod),
                     (tensor.conjugate() @ tensor).array)

    @staticmethod
    def classical(tensor):
        return CQMap(C(tensor.dom), C(tensor.cod), tensor.array)

    @staticmethod
    def discard(dom):
        array = np.tensordot(
            np.ones(dom.classical), Tensor.id(dom.quantum).array, 0)
        return CQMap(dom, CQ(), array)

    def is_close(self, other):
        return isinstance(other, CQMap)\
            and (self.dom, self.cod) == (other.dom, other.cod)\
            and np.allclose(self.array, other.array)

    @property
    def is_causal(self):
        return self.discard(self.dom).is_close(self >> self.discard(self.cod))

    @staticmethod
    def cups(left, right):
        return CQMap.classical(Tensor.cups(left.classical, right.classical))\
            @ CQMap.pure(Tensor.cups(left.quantum, right.quantum))

    @staticmethod
    def caps(left, right):
        return CQMap.cups(left, right).dagger()


class CQMapFunctor(rigid.Functor):
    """
    Implements functors into :class:`CQMap`.
    """
    def __init__(self, ob, ar):
        super().__init__(ob, ar, ob_factory=CQ, ar_factory=CQMap)

    def __repr__(self):
        return super().__repr__().replace("Functor", "CQMapFunctor")

    def __call__(self, diagram):
        if isinstance(diagram, PureBox):
            if diagram.classical:
                dom, cod = self(diagram.dom), self(diagram.cod)
                return CQMap(dom, cod, diagram.array)
            dom, cod = self(diagram.dom).quantum, self(diagram.cod).quantum
            return CQMap.pure(Tensor(dom, cod, diagram.array))
        if isinstance(diagram, Swap):
            return CQMap.swap(self(diagram.dom[:1]), self(diagram.dom[1:]))
        if isinstance(diagram, Discard):
            return CQMap.discard(self(diagram.dom))
        if isinstance(diagram, MixedState):
            return CQMap.discard(self(diagram.cod)).dagger()
        if isinstance(diagram, Measure):
            return CQMap.measure(
                self(diagram.dom).quantum, destructive=diagram.destructive)
        if isinstance(diagram, Encode):
            return CQMap.encode(
                self(diagram.dom).classical, constructive=diagram.constructive)
        return super().__call__(diagram)


class BitsAndQubits(Ty):
    """
    Implements the objects of :class:`Circuit`, the free monoid on two objects
    :code:`bit` and :code:`qubit`.

    Examples
    --------
    >>> assert bit == BitsAndQubits("bit")
    >>> assert qubit == BitsAndQubits("qubit")
    >>> assert bit @ qubit != qubit @ bit

    You can construct :code:`n` qubits by taking powers of :code:`qubit`:

    >>> bit @ bit @ qubit @ qubit @ qubit
    bit ** 2 @ qubit ** 3
    """
    @staticmethod
    def _upgrade(ty):
        return BitsAndQubits(*ty.objects)

    def __repr__(self):
        if not self:
            return "Ty()"
        n_bits = len(list(takewhile(lambda x: x.name == "bit", self.objects)))
        n_qubits = len(list(takewhile(
            lambda x: x.name == "qubit", self.objects[n_bits:])))
        remainder = self.objects[n_bits + n_qubits:]
        left = "" if not n_bits else "bit{}".format(
            " ** {}".format(n_bits) if n_bits > 1 else "")
        middle = "" if not n_qubits else "qubit{}".format(
            " ** {}".format(n_qubits) if n_qubits > 1 else "")
        right = "" if not remainder else repr(BitsAndQubits(*remainder))
        return " @ ".join(s for s in [left, middle, right] if s)

    def __str__(self):
        return repr(self)

    @property
    def l(self):
        return BitsAndQubits(*self.objects[::-1])

    @property
    def r(self):
        return self.l


class Circuit(Diagram):
    """
    Implements classical-quantum circuits.
    """
    @staticmethod
    def _upgrade(diagram):
        dom, cod = BitsAndQubits(*diagram.dom), BitsAndQubits(*diagram.cod)
        return Circuit(
            dom, cod, diagram.boxes, diagram.offsets, diagram.layers)

    def __repr__(self):
        return super().__repr__().replace('Diagram', 'Circuit')

    def draw(self, **params):
        draw_types = params.get('draw_types') or self.is_mixed
        return super().draw(**dict(params, draw_types=draw_types))

    @staticmethod
    def id(dom):
        return Id(dom)

    @staticmethod
    def swap(left, right):
        return monoidal.swap(left, right,
                             ar_factory=Circuit, swap_factory=Swap)

    @staticmethod
    def permutation(perm, dom=None):
        return permutation(perm, dom)

    @staticmethod
    def cups(left, right):
        assert all(x.name == "qubit" for x in left @ right)
        cup = CX >> H @ sqrt(2) @ Id(1) >> Bra(0, 0)
        return rigid.cups(
            left, right, ar_factory=Circuit, cup_factory=lambda *_: cup)

    @staticmethod
    def caps(left, right):
        return Circuit.cups(left, right).dagger()

    @property
    def is_mixed(self):
        """
        Whether the circuit is mixed, i.e. it contains both bits and qubits
        or it discards qubits. Mixed circuits can be evaluated only by a
        :class:`CQMapFunctor` not a :class:`discopy.tensor.TensorFunctor`.
        """
        both_bits_and_qubits = self.dom.count(bit) and self.dom.count(qubit)
        return both_bits_and_qubits or any(box.is_mixed for box in self.boxes)

    def eval(self, backend=None, mixed=False, **params):
        """
        Parameters
        ----------
        mixed : bool, optional
            Whether to apply :class:`TensorFunctor` or :class:`CQMapFunctor`.
        backend : pytket.Backend, optional
            Backend on which to run the circuit, if none then `numpy`.
        params : optional
            Get passed to Circuit.get_counts.

        Returns
        -------
        cqmap : :class:`CQMap`
            If :code:`mixed=True` and :code:`backend=None`.
        tensor : :class:`discopy.tensor.Tensor`
            Otherwise.

        Examples
        --------
        We can evaluate a pure circuit (i.e. with :code:`not circuit.is_mixed`)
        as a unitary :class:`discopy.tensor.Tensor` or as a :class:`CQMap`:

        >>> H.eval()  # doctest: +ELLIPSIS
        Tensor(dom=Dim(2), cod=Dim(2), array=[0.7..., 0.7..., 0.7..., -0.7...])
        >>> H.eval(mixed=True)  # doctest: +ELLIPSIS
        CQMap(dom=Q(Dim(2)), cod=Q(Dim(2)), array=[0.499..., 0.499...])

        We can evaluate a mixed circuit as a :class:`CQMap`:

        >>> circuit = Bits(1, 0) @ Ket(0) >> Discard(bit ** 2 @ qubit)
        >>> circuit.eval()
        CQMap(dom=CQ(), cod=CQ(), array=[1.0])
        >>> Measure().eval()
        CQMap(dom=Q(Dim(2)), cod=C(Dim(2)), array=[1, 0, 0, 0, 0, 0, 0, 1])

        We can execute any circuit on a `pytket.Backend`:

        >>> circuit = Ket(0, 0) >> sqrt(2) @ H @ X >> CX >> Measure() @ Bra(0)
        >>> from unittest.mock import Mock
        >>> backend = Mock()
        >>> backend.get_counts.return_value = {(0, 1): 512, (1, 0): 512}
        >>> circuit.eval(backend, n_shots=2**10)  # doctest: +ELLIPSIS
        Tensor(dom=Dim(1), cod=Dim(2), array=[0.0, 0.999...])
        """
        if backend is None and (mixed or self.is_mixed):
            ob, ar = {Ty('bit'): C(Dim(2)), Ty('qubit'): Q(Dim(2))}, {}
            return CQMapFunctor(ob, ar)(self)
        if backend is None:
            ob, ar = {Ty('bit'): 2, Ty('qubit'): 2}, lambda g: g.array
            return TensorFunctor(ob, ar)(self)
        counts = self.get_counts(backend, **params)
        n_bits = len(list(counts.keys()).pop())
        array = np.zeros(n_bits * (2, ))
        for bitstring, count in counts.items():
            array += count * Ket(*bitstring).array
        return Tensor(Dim(1), Dim(*(n_bits * (2, ))), array)

    def get_counts(self, backend=None, **params):
        """
        Parameters
        ----------
        backend : pytket.Backend, optional
            Backend on which to run the circuit, if none then `numpy`.
        n_shots : int, optional
            Number of shots, default is :code:`2**10`.
        measure_all : bool, optional
            Whether to measure all qubits, default is :code:`False`.
        normalize : bool, optional
            Whether to normalize the counts, default is :code:`True`.
        post_select : bool, optional
            Whether to perform post-selection, default is :code:`True`.
        scale : bool, optional
            Whether to scale the output, default is :code:`True`.
        seed : int, optional
            Seed to feed the backend, default is :code:`None`.
        compilation : callable, optional
            Compilation function to apply before getting counts.

        Returns
        -------
        counts : dict
            From bitstrings to counts.

        Examples
        --------
        >>> circuit = H @ X >> CX >> Measure(2)
        >>> from unittest.mock import Mock
        >>> backend = Mock()
        >>> backend.get_counts.return_value = {(0, 1): 512, (1, 0): 512}
        >>> circuit.get_counts(backend, n_shots=2**10)  # doctest: +ELLIPSIS
        {(0, 1): 0.5, (1, 0): 0.5}
        """
        if backend is None:
            tensor, counts = self.eval(backend=None), dict()
            for i in range(2**len(tensor.cod)):
                bits = index2bitstring(i, len(tensor.cod))
                if tensor.array[bits]:
                    counts[bits] = float(tensor.array[bits])
            return counts
        from discopy.tk import get_counts
        return get_counts(self, backend, **params)


    def measure(self, mixed=False):
        """
        Measures a circuit on the computational basis.

        Returns
        -------
        array : np.ndarray
            with real entries and the same shape as :code:`self.eval().array`.

        Examples
        --------
        >>> m = X.measure()
        >>> list(np.round(m.flatten()))
        [0.0, 1.0, 1.0, 0.0]
        >>> assert (Ket(0) >> X >> Bra(1)).measure() == m[0, 1]
        """
        if mixed or self.is_mixed:
            encode = Id(0).tensor(*(
                Encode() if x in qubit else Id(bit) for x in self.dom))
            measure = Id(0).tensor(*(
                Measure() if x in qubit else Id(bit) for x in self.cod))
            return (encode >> self >> measure).eval().array.real
        process = self.eval()
        states, effects = [], []
        states = [Ket(*index2bitstring(i, len(self.dom))).eval()
                  for i in range(2 ** len(self.dom))]
        effects = [Bra(*index2bitstring(j, len(self.cod))).eval()
                   for j in range(2 ** len(self.cod))]
        array = np.zeros(len(self.dom + self.cod) * (2, ))
        for state in states if self.dom else [Tensor.id(1)]:
            for effect in effects if self.cod else [Tensor.id(1)]:
                scalar = np.absolute((state >> process >> effect).array) ** 2
                array += scalar * (state.dagger() >> effect.dagger()).array
        return array

    def to_tk(self):
        """
        Returns
        -------
        tk_circuit : pytket.Circuit
            A :class:`pytket.Circuit`.

        Note
        ----
        * No measurements are performed.
        * SWAP gates are treated as logical swaps.
        * If the circuit contains scalars or a :class:`Bra`,
          then :code:`tk_circuit` will hold attributes
          :code:`post_selection` and :code:`scalar`.

        Examples
        --------
        >>> circuit0 = sqrt(2) @ H @ Rx(0.5) >> CX >> Measure() @ Discard()
        >>> circuit0.to_tk()  # doctest: +ELLIPSIS
        tk.Circuit(2, 1).H(0).Rx(1.0, 1).CX(0, 1).Measure(0, 0).scale(1.41...)

        >>> circuit1 = Ket(1, 0) >> CX >> Id(1) @ Ket(0) @ Id(1)
        >>> circuit1.to_tk()
        tk.Circuit(3).X(0).CX(0, 2)

        >>> circuit2 = X @ Id(2) >> Id(1) @ SWAP >> CX @ Id(1) >> Id(1) @ SWAP
        >>> circuit2.to_tk()
        tk.Circuit(3).X(0).CX(0, 2)

        >>> circuit3 = Ket(0, 0)\\
        ...     >> H @ Id(1)\\
        ...     >> Id(1) @ X\\
        ...     >> CX\\
        ...     >> Id(1) @ Bra(0)
        >>> print(repr(circuit3.to_tk()))
        tk.Circuit(2, 1).H(0).X(1).CX(0, 1).Measure(1, 0).post_select({0: 0})

        """
        from discopy.tk import to_tk
        return to_tk(self)

    @staticmethod
    def from_tk(tk_circuit):
        """
        Parameters
        ----------
        tk_circuit : pytket.Circuit
            A pytket.Circuit, potentially with :code:`scalar` and
            :code:`post_selection` attributes.

        Returns
        -------
        circuit : :class:`Circuit`
            Such that :code:`Circuit.from_tk(circuit.to_tk()) == circuit`.

        Note
        ----
        * SWAP gates are introduced when applying gates to non-adjacent qubits.

        Examples
        --------
        >>> c1 = Rz(0.5) @ Id(1) >> Id(1) @ Rx(0.25) >> CX
        >>> c2 = Circuit.from_tk(c1.to_tk())
        >>> assert c1.normal_form() == c2.normal_form()

        >>> import pytket as tk
        >>> tk_GHZ = tk.Circuit(3).H(1).CX(1, 2).CX(1, 0)
        >>> print(Circuit.from_tk(tk_GHZ))
        Id(1) @ H @ Id(1)\\
          >> Id(1) @ CX\\
          >> SWAP @ Id(1)\\
          >> CX @ Id(1)\\
          >> SWAP @ Id(1)
        >>> circuit = Ket(1, 0) >> CX >> Id(1) @ Ket(0) @ Id(1)
        >>> print(Circuit.from_tk(circuit.to_tk()))
        X @ Id(2) >> Id(1) @ SWAP >> CX @ Id(1) >> Id(1) @ SWAP

        >>> bell_state = Circuit.caps(PRO(1), PRO(1))
        >>> bell_effect = bell_state[::-1]
        >>> circuit = bell_state @ Id(1) >> Id(1) @ bell_effect >> Bra(0)
        >>> print(Circuit.from_tk(circuit.to_tk()))
        H @ Id(2)\\
          >> CX @ Id(1)\\
          >> Id(1) @ CX\\
          >> Id(1) @ H @ Id(1)\\
          >> Id(2) @ Bra(0)\\
          >> Id(1) @ Bra(0)\\
          >> Bra(0)\\
          >> scalar(2.000)
        """
        from discopy.tk import from_tk
        return from_tk(tk_circuit)


class Id(rigid.Id, Circuit):
    def __init__(self, dom):
        if isinstance(dom, int):
            dom = qubit ** dom
        self._qubit_only = all(x.name == "qubit" for x in dom)
        rigid.Id.__init__(self, dom)
        Circuit.__init__(self, dom, dom, [], [])

    def __repr__(self):
        return "Id({})".format(len(self.dom) if self._qubit_only else self.dom)

    def __str__(self):
        return repr(self)


class Box(rigid.Box, Circuit):
    def __init__(self, name, dom, cod, data=None, _dagger=False):
        rigid.Box.__init__(self, name, dom, cod, data=data, _dagger=_dagger)
        Circuit.__init__(self, dom, cod, [self], [0])

    def __repr__(self):
        return self.name


class PureBox(Box):
    def __init__(self, name, dom, cod, data=None, _dagger=False):
        if all(x.name == "bit" for x in dom @ cod):
            self.classical = True
        elif all(x.name == "qubit" for x in dom @ cod):
            self.classical = False
        else:
            raise ValueError("dom and cod should be bits only or qubits only.")
        super().__init__(name, dom, cod, data=data, _dagger=_dagger)

    @property
    def is_mixed(self):
        return False


class MixedBox(Box):
    @property
    def is_mixed(self):
        return True


class Swap(rigid.Swap, Box):
    @property
    def is_mixed(self):
        return self.left != self.right

    def dagger(self):
        return Swap(self.right, self.left)

    def __repr__(self):
        return "SWAP"\
            if self.left == self.right == qubit else super().__repr__()

    def __str__(self):
        return repr(self)


class Discard(MixedBox):
    def __init__(self, dom=1):
        if isinstance(dom, int):
            dom = qubit ** dom
        super().__init__("Discard({})".format(dom), dom, qubit ** 0)

    def dagger(self):
        return MixedState(self.dom)

    @property
    def is_mixed(self):
        return True


class MixedState(MixedBox):
    def __init__(self, cod=1):
        if isinstance(cod, int):
            cod = qubit ** cod
        super().__init__("MixedState({})".format(cod), qubit ** 0, cod)

    def dagger(self):
        return Discard(self.cod)


class Measure(MixedBox):
    def __init__(self, n_qubits=1, destructive=True):
        if destructive:
            dom, cod = qubit ** n_qubits, bit ** n_qubits
            name = "Measure({})".format(n_qubits)
        else:
            dom, cod = qubit ** n_qubits, qubit ** n_qubits @ bit ** n_qubits
            name = "Measure({}, destructive=False)".format(n_qubits)
        super().__init__(name, dom, cod)
        self.destructive = destructive

    def dagger(self):
        return Encode(len(self.cod), constructive=self.destructive)


class Encode(MixedBox):
    def __init__(self, n_bits=1, constructive=True):
        if constructive:
            dom, cod = bit ** n_bits, qubit ** n_bits
            name = "Encode({})".format(n_bits)
        else:
            dom, cod = qubit ** n_bits @ bit ** n_bits, qubit ** n_bits
            name = "Encode({}, constructive=False)".format(n_bits)
        super().__init__(name, dom, cod)
        self.constructive = constructive

    def dagger(self):
        return Measure(len(self.dom), destructive=self.constructive)


class Spider(PureBox):
    def __init__(self, n_legs_in, n_legs_out, axis='X', classical=False):
        self.axis = axis
        ob = bit if classical else qubit
        dom, cod = ob ** n_legs_in, ob ** n_legs_out
        name = "Spider({}, {}{}{})".format(
            len(dom), len(cod),
            ", axis=X" if axis == 'X' else "",
            ", classical=True" if classical else "")
        super().__init__(name, dom, cod)

    def dagger(self):
        return Spider(len(self.cod), len(self.dom), axis=self.axis)

    @property
    def array(self):
        zeros = Bra(*(len(self.dom) * [0])) >> Ket(*(len(self.cod) * [0]))
        ones = Bra(*(len(self.dom) * [1])) >> Ket(*(len(self.cod) * [1]))
        return zeros.eval().array + ones.eval().array


class QGate(PureBox):
    def __init__(self, name, n_qubits, array=None, _dagger=False):
        dom = qubit ** n_qubits
        if array is not None:
            self._array = np.array(array).reshape(2 * n_qubits * (2, ) or 1)
        super().__init__(name, dom, dom, _dagger=_dagger)

    @property
    def array(self):
        return self._array

    def __repr__(self):
        if self in gates:
            return self.name
        return "QGate({}, n_qubits={}, array={})".format(
            repr(self.name), len(self.dom),
            np.array2string(self.array.flatten()))

    def dagger(self):
        return QGate(
            self.name, len(self.dom), self.array,
            _dagger=None if self._dagger is None else not self._dagger)


class CGate(PureBox):
    def __init__(self, name, n_bits_in, n_bits_out, array, _dagger=False):
        dom, cod = bit ** n_bits_in, bit ** n_bits_out
        if array is not None:
            self._array = np.array(array).reshape(
                (n_bits_in + n_bits_out) * (2, ) or 1)
        super().__init__(name, dom, cod, _dagger=_dagger)

    @property
    def array(self):
        return self._array

    def __repr__(self):
        return "CGate({}, n_bits_in={}, n_bits_out={}, array={})".format(
            repr(self.name), len(self.dom), len(self.cod),
            np.array2string(self.array.flatten()))

    def dagger(self):
        return CGate(
            self.name, len(self.dom), len(self.cod), self.array,
            _dagger=None if self._dagger is None else not self._dagger)

    @staticmethod
    def func(name, n_bits_in, n_bits_out, function):
        array = np.zeros((n_bits_in + n_bits_out) * [2])
        for i in range(2 ** n_bits_in):
            bitstring = tuple(map(int, format(i, '0{}b'.format(n_bits_in))))
            array[bitstring + tuple(function(*bitstring))] = 1
        return CGate(name, n_bits_in, n_bits_out, array)


class Bits(CGate):
    def __init__(self, *bitstring, _dagger=False):
        data = Tensor.id(Dim(1)).tensor(*(
            Tensor(Dim(1), Dim(2), [0, 1] if bit else [1, 0])
            for bit in bitstring))
        name = "Bits({})".format(', '.join(map(str, bitstring)))
        dom, cod = (len(bitstring), 0) if _dagger else (0, len(bitstring))
        super().__init__(name, dom, cod, array=data.array, _dagger=_dagger)
        self.bitstring = bitstring

    def __repr__(self):
        return self.name + (".dagger()" if self._dagger else "")

    def dagger(self):
        return Bits(*self.bitstring, _dagger=not self._dagger)


class Ket(PureBox):
    def __init__(self, *bitstring):
        dom, cod = qubit ** 0, qubit ** len(bitstring)
        name = "Ket({})".format(', '.join(map(str, bitstring)))
        super().__init__(name, dom, cod)
        self.bitstring = bitstring
        self.array = Bits(*bitstring).array

    def dagger(self):
        return Bra(*self.bitstring)


class Bra(PureBox):
    def __init__(self, *bitstring):
        name = "Bra({})".format(', '.join(map(str, bitstring)))
        dom, cod = qubit ** len(bitstring), qubit ** 0
        super().__init__(name, dom, cod)
        self.bitstring = bitstring
        self.array = Bits(*bitstring).array

    def dagger(self):
        return Ket(*self.bitstring)


class Rotation(QGate):
    def __init__(self, name, phase, n_qubits=1):
        self._phase = phase
        super().__init__(name, n_qubits, array=None)

    @property
    def phase(self):
        return self._phase

    @property
    def name(self):
        return '{}({})'.format(self._name, self.phase)

    def dagger(self):
        return type(self)(-self.phase)

    def __repr__(self):
        return self.name


class Rx(Rotation):
    def __init__(self, phase):
        super().__init__("Rx", phase)

    @property
    def array(self):
        half_theta = np.pi * self.phase
        global_phase = np.exp(1j * half_theta)
        sin, cos = np.sin(half_theta), np.cos(half_theta)
        return global_phase * np.array([[cos, -1j * sin], [-1j * sin, cos]])


class Rz(Rotation):
    def __init__(self, phase):
        super().__init__("Rz", phase)

    @property
    def array(self):
        theta = 2 * np.pi * self.phase
        return np.array([[1, 0], [0, np.exp(1j * theta)]])


class CRz(Rotation):
    def __init__(self, phase):
        super().__init__("CRz", phase, n_qubits=2)

    @property
    def array(self):
        phase = np.exp(1j * 2 * np.pi * self.phase)
        return np.array([1, 0, 0, 0,
                         0, 1, 0, 0,
                         0, 0, 1, 0,
                         0, 0, 0, phase])


class CircuitFunctor(rigid.Functor):
    def __init__(self, ob, ar):
        super().__init__(ob, ar, ob_factory=BitsAndQubits, ar_factory=Circuit)

    def __repr__(self):
        return super().__repr__().replace("Functor", "CircuitFunctor")


bit, qubit = BitsAndQubits("bit"), BitsAndQubits("qubit")

SWAP = Swap(qubit, qubit)
CX = QGate('CX', 2, [1, 0, 0, 0,
                     0, 1, 0, 0,
                     0, 0, 0, 1,
                     0, 0, 1, 0], _dagger=None)
CZ = QGate('CZ', 2, [1, 0, 0, 0,
                     0, 1, 0, 0,
                     0, 0, 1, 0,
                     0, 0, 0, -1], _dagger=None)
H = QGate('H', 1, 1 / np.sqrt(2) * np.array([1, 1, 1, -1]), _dagger=None)
S = QGate('S', 1, [1, 0, 0, 1j])
T = QGate('T', 1, [1, 0, 0, np.exp(1j * np.pi / 4)])
X = QGate('X', 1, [0, 1, 1, 0], _dagger=None)
Y = QGate('Y', 1, [0, -1j, 1j, 0])
Z = QGate('Z', 1, [1, 0, 0, -1], _dagger=None)

gates = [SWAP, CZ, CX, H, S, T, X, Y, Z]


def permutation(perm, dom=None):
    if dom is None:
        dom = qubit ** len(perm)
    return monoidal.permutation(perm, dom, ar_factory=Circuit)


def sqrt(real_number):
    name = 'sqrt({})'.format(real_number)
    return QGate(name, 0, math.sqrt(real_number), _dagger=None)


def scalar(complex_number):
    name = 'scalar({:.3f})'.format(complex_number)
    _dagger = None if np.conjugate(complex_number) == complex_number else False
    return QGate(name, 0, complex_number, _dagger=_dagger)


def random_tiling(n_qubits, depth=3, gateset=[H, Rx, CX], seed=None):
    """ Returns a random Euler decomposition if n_qubits == 1,
    otherwise returns a random tiling with the given depth and gateset.

    >>> c = random_tiling(1, seed=420)
    >>> print(c)  # doctest: +ELLIPSIS
    Rx(0.026...>> Rz(0.781... >> Rx(0.272...
    >>> print(random_tiling(2, 2, gateset=[CX, H, T], seed=420))
    CX >> T @ Id(1) >> Id(1) @ T
    >>> print(random_tiling(3, 2, gateset=[CX, H, T], seed=420))
    CX @ Id(1) >> Id(2) @ T >> H @ Id(2) >> Id(1) @ H @ Id(1) >> Id(2) @ H
    >>> print(random_tiling(2, 1, gateset=[Rz, Rx], seed=420))
    Rz(0.6731171219152886) @ Id(1) >> Id(1) @ Rx(0.2726063832840899)
    """
    if seed is not None:
        random.seed(seed)
    if n_qubits == 1:
        phases = [random.random() for _ in range(3)]
        return Rx(phases[0]) >> Rz(phases[1]) >> Rx(phases[2])
    result = Id(n_qubits)
    for _ in range(depth):
        line, n_affected = Id(0), 0
        while n_affected < n_qubits:
            gate = random.choice(
                gateset if n_qubits - n_affected > 1 else [
                    g for g in gateset
                    if g is Rx or g is Rz or len(g.dom) == 1])
            if gate is Rx or gate is Rz:
                gate = gate(random.random())
            line = line @ gate
            n_affected += len(gate.dom)
        result = result >> line
    return result


def IQPansatz(n_qubits, params):
    """
    Builds an IQP ansatz on n qubits, if n = 1 returns an Euler decomposition

    >>> print(IQPansatz(3, [[0.1, 0.2], [0.3, 0.4]]))
    H @ Id(2)\\
      >> Id(1) @ H @ Id(1)\\
      >> Id(2) @ H\\
      >> CRz(0.1) @ Id(1)\\
      >> Id(1) @ CRz(0.2)\\
      >> H @ Id(2)\\
      >> Id(1) @ H @ Id(1)\\
      >> Id(2) @ H\\
      >> CRz(0.3) @ Id(1)\\
      >> Id(1) @ CRz(0.4)
    >>> print(IQPansatz(1, [0.3, 0.8, 0.4]))
    Rx(0.3) >> Rz(0.8) >> Rx(0.4)
    """
    def layer(thetas):
        hadamards = Id(0).tensor(*(n_qubits * [H]))
        rotations = Id(n_qubits).then(*(
            Id(i) @ CRz(thetas[i]) @ Id(n_qubits - 2 - i)
            for i in range(n_qubits - 1)))
        return hadamards >> rotations
    if n_qubits == 1:
        return Rx(params[0]) >> Rz(params[1]) >> Rx(params[2])
    if np.shape(params)[1] != n_qubits - 1:
        raise ValueError(
            "Expected params of shape (depth, {})".format(n_qubits - 1))
    depth = np.shape(params)[0]
    return Id(n_qubits).then(*(layer(params[i]) for i in range(depth)))