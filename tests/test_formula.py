import pytest

from komado.formula import Engine, FormulaError, parse_ref, ref_to_a1


class TestRefs:
    def test_a1(self):
        assert parse_ref("A1") == (0, 0)

    def test_lower_case(self):
        assert parse_ref("c10") == (9, 2)

    def test_double_letters(self):
        assert parse_ref("AA1") == (0, 26)

    def test_round_trip(self):
        for ref in [(0, 0), (9, 25), (99, 26), (3, 700)]:
            assert parse_ref(ref_to_a1(ref)) == ref

    @pytest.mark.parametrize("text", ["A0", "1A", "A", "1", "A1B", ""])
    def test_invalid(self, text):
        with pytest.raises(FormulaError):
            parse_ref(text)


class TestLiterals:
    def test_number(self):
        engine = Engine()
        engine.set_cell("A1", "42")
        assert engine.value("A1") == 42.0

    def test_text(self):
        engine = Engine()
        engine.set_cell("A1", "家賃")
        assert engine.value("A1") == "家賃"

    def test_empty_cell(self):
        assert Engine().value("Z99") == ""

    def test_clearing(self):
        engine = Engine()
        engine.set_cell("A1", "42")
        engine.set_cell("A1", "")
        assert engine.value("A1") == ""
        assert engine.refs() == set()


class TestArithmetic:
    @pytest.mark.parametrize(
        ("formula", "expected"),
        [
            ("=1+2", 3.0),
            ("=2*3+4", 10.0),
            ("=2+3*4", 14.0),
            ("=(2+3)*4", 20.0),
            ("=10/4", 2.5),
            ("=-5+2", -3.0),
            ("=--3", 3.0),
            ("= 1 + 2 ", 3.0),
        ],
    )
    def test_evaluation(self, formula, expected):
        engine = Engine()
        engine.set_cell("A1", formula)
        assert engine.value("A1") == expected

    def test_division_by_zero(self):
        engine = Engine()
        engine.set_cell("A1", "=1/0")
        assert engine.value("A1") == "#DIV/0!"

    def test_reference(self):
        engine = Engine()
        engine.set_cell("A1", "10")
        engine.set_cell("B1", "=A1*3")
        assert engine.value("B1") == 30.0

    def test_empty_reference_is_zero(self):
        engine = Engine()
        engine.set_cell("A1", "=B1+5")
        assert engine.value("A1") == 5.0

    def test_text_reference_is_value_error(self):
        engine = Engine()
        engine.set_cell("A1", "備考")
        engine.set_cell("B1", "=A1+1")
        assert engine.value("B1") == "#VALUE!"


class TestFunctions:
    @pytest.fixture
    def engine(self):
        engine = Engine()
        engine.set_cell("A1", "10")
        engine.set_cell("A2", "20")
        engine.set_cell("A3", "30")
        return engine

    def test_sum_range(self, engine):
        engine.set_cell("B1", "=SUM(A1:A3)")
        assert engine.value("B1") == 60.0

    def test_sum_skips_text_and_empty(self, engine):
        engine.set_cell("A4", "メモ")
        engine.set_cell("B1", "=SUM(A1:A5)")
        assert engine.value("B1") == 60.0

    def test_average(self, engine):
        engine.set_cell("B1", "=AVERAGE(A1:A3)")
        assert engine.value("B1") == 20.0

    def test_min_max(self, engine):
        engine.set_cell("B1", "=MAX(A1:A3)-MIN(A1:A3)")
        assert engine.value("B1") == 20.0

    def test_count(self, engine):
        engine.set_cell("B1", "=COUNT(A1:A3)")
        assert engine.value("B1") == 3.0

    def test_mixed_args(self, engine):
        engine.set_cell("B1", "=SUM(A1:A3, 40)")
        assert engine.value("B1") == 100.0

    def test_case_insensitive(self, engine):
        engine.set_cell("B1", "=sum(a1:a3)")
        assert engine.value("B1") == 60.0

    def test_abs(self):
        engine = Engine()
        engine.set_cell("A1", "=ABS(-7)")
        assert engine.value("A1") == 7.0

    def test_round(self):
        engine = Engine()
        engine.set_cell("A1", "=ROUND(3.14159, 2)")
        assert engine.value("A1") == 3.14

    def test_round_to_integer(self):
        engine = Engine()
        engine.set_cell("A1", "=ROUND(2.5)")
        assert engine.value("A1") == 2.0

    def test_unknown_function(self):
        engine = Engine()
        engine.set_cell("A1", "=VLOOKUP(1, 2)")
        assert engine.value("A1") == "#NAME?"

    def test_error_propagates_through_range(self, engine):
        engine.set_cell("A2", "=1/0")
        engine.set_cell("B1", "=SUM(A1:A3)")
        assert engine.value("B1") == "#DIV/0!"


class TestCycles:
    def test_self_reference(self):
        engine = Engine()
        engine.set_cell("A1", "=A1+1")
        assert engine.value("A1") == "#CYCLE!"

    def test_mutual_reference(self):
        engine = Engine()
        engine.set_cell("A1", "=B1")
        engine.set_cell("B1", "=A1")
        assert engine.value("A1") == "#CYCLE!"
        assert engine.value("B1") == "#CYCLE!"

    def test_cycle_via_range(self):
        engine = Engine()
        engine.set_cell("A1", "=SUM(A1:A3)")
        assert engine.value("A1") == "#CYCLE!"


class TestParseErrors:
    @pytest.mark.parametrize(
        "formula",
        ["=1+", "=(1+2", "=SUM(1,", "=1 2", "=@", "=A1:B2", "=SUM()"],
    )
    def test_error_code(self, formula):
        engine = Engine()
        engine.set_cell("A1", formula)
        assert engine.value("A1") == "#ERROR!"


class TestDisplay:
    def test_integral_float_has_no_point(self):
        engine = Engine()
        engine.set_cell("A1", "=1+2")
        assert engine.display("A1") == "3"

    def test_fraction_is_compact(self):
        engine = Engine()
        engine.set_cell("A1", "=10/4")
        assert engine.display("A1") == "2.5"

    def test_text_as_is(self):
        engine = Engine()
        engine.set_cell("A1", "家賃")
        assert engine.display("A1") == "家賃"

    def test_empty(self):
        assert Engine().display("A1") == ""


class TestComparisons:
    @pytest.mark.parametrize(
        ("formula", "expected"),
        [
            ("=1<2", 1.0),
            ("=2<1", 0.0),
            ("=3=3", 1.0),
            ("=3<>3", 0.0),
            ("=2<>3", 1.0),
            ("=3>=3", 1.0),
            ("=4<=3", 0.0),
            ("=1+1=2", 1.0),
        ],
    )
    def test_compare(self, formula, expected):
        engine = Engine()
        engine.set_cell("A1", formula)
        assert engine.value("A1") == expected

    def test_compares_references(self):
        engine = Engine()
        engine.set_cell("A1", "10")
        engine.set_cell("A2", "20")
        engine.set_cell("B1", "=A1<A2")
        assert engine.value("B1") == 1.0


class TestIf:
    def test_true_branch(self):
        engine = Engine()
        engine.set_cell("A1", "=IF(1<2, 10, 20)")
        assert engine.value("A1") == 10.0

    def test_false_branch(self):
        engine = Engine()
        engine.set_cell("A1", "=IF(1>2, 10, 20)")
        assert engine.value("A1") == 20.0

    def test_dead_branch_is_not_evaluated(self):
        engine = Engine()
        engine.set_cell("A1", "=IF(1=1, 5, 1/0)")
        assert engine.value("A1") == 5.0

    def test_nested(self):
        engine = Engine()
        engine.set_cell("A1", "5")
        engine.set_cell("B1", "=IF(A1>=10, 2, IF(A1>=3, 1, 0))")
        assert engine.value("B1") == 1.0

    def test_wrong_arity(self):
        engine = Engine()
        engine.set_cell("A1", "=IF(1, 2)")
        assert engine.value("A1") == "#ERROR!"


class TestMoreFunctions:
    @pytest.fixture
    def engine(self):
        engine = Engine()
        for ref, val in [("A1", "10"), ("A2", "20"), ("A3", "30")]:
            engine.set_cell(ref, val)
        return engine

    def test_median(self, engine):
        engine.set_cell("B1", "=MEDIAN(A1:A3)")
        assert engine.value("B1") == 20.0

    def test_product(self, engine):
        engine.set_cell("B1", "=PRODUCT(A1:A3)")
        assert engine.value("B1") == 6000.0

    def test_stdev(self, engine):
        engine.set_cell("B1", "=STDEV(A1:A3)")
        assert engine.value("B1") == 10.0

    def test_stdev_needs_two_values(self):
        engine = Engine()
        engine.set_cell("A1", "5")
        engine.set_cell("B1", "=STDEV(A1)")
        assert engine.value("B1") == "#ERROR!"

    @pytest.mark.parametrize(
        ("formula", "expected"),
        [
            ("=SQRT(16)", 4.0),
            ("=POWER(2, 10)", 1024.0),
            ("=MOD(17, 5)", 2.0),
            ("=FLOOR(3.7)", 3.0),
            ("=CEIL(3.2)", 4.0),
            ("=INT(-3.7)", -3.0),
            ("=SIGN(-9)", -1.0),
            ("=SIGN(0)", 0.0),
        ],
    )
    def test_scalars(self, formula, expected):
        engine = Engine()
        engine.set_cell("A1", formula)
        assert engine.value("A1") == expected

    def test_sqrt_negative_is_error(self):
        engine = Engine()
        engine.set_cell("A1", "=SQRT(-1)")
        assert engine.value("A1") == "#ERROR!"

    def test_mod_by_zero(self):
        engine = Engine()
        engine.set_cell("A1", "=MOD(5, 0)")
        assert engine.value("A1") == "#DIV/0!"

    def test_power_complex_is_error(self):
        engine = Engine()
        engine.set_cell("A1", "=POWER(-8, 0.5)")
        assert engine.value("A1") == "#ERROR!"


class TestEdges:
    def test_deeply_nested_if(self):
        engine = Engine()
        engine.set_cell("A1", "3")
        engine.set_cell("B1", "=IF(A1=1,10,IF(A1=2,20,IF(A1=3,30,0)))")
        assert engine.value("B1") == 30.0

    def test_whitespace_heavy_formula(self):
        engine = Engine()
        engine.set_cell("A1", "=  SUM ( 1 , 2 , 3 )  ")
        assert engine.value("A1") == 6.0

    def test_bare_equals_is_error(self):
        engine = Engine()
        engine.set_cell("A1", "=")
        assert engine.value("A1") == "#ERROR!"

    def test_comparison_inside_arithmetic(self):
        engine = Engine()
        engine.set_cell("A1", "=(2>1)+(3>5)")
        assert engine.value("A1") == 1.0


class TestRecalculation:
    def test_dependents_update_after_set(self):
        engine = Engine()
        engine.set_cell("A1", "10")
        engine.set_cell("B1", "=A1*2")
        assert engine.value("B1") == 20.0
        engine.set_cell("A1", "50")
        assert engine.value("B1") == 100.0

    def test_cycle_recovers_after_fix(self):
        engine = Engine()
        engine.set_cell("A1", "=B1")
        engine.set_cell("B1", "=A1")
        assert engine.value("A1") == "#CYCLE!"
        engine.set_cell("B1", "5")
        assert engine.value("A1") == 5.0
