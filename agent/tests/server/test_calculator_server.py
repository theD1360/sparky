import os
import sys
import unittest

# Add the src directory to the Python path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)

from tools.calculator.server import (
    abs,
    acos,
    add,
    asin,
    atan,
    ceil,
    cos,
    cosh,
    divide,
    factorial,
    floor,
    log,
    log2,
    log10,
    multiply,
    power,
    sin,
    sinh,
    sqrt,
    subtract,
    tan,
    tanh,
)
from models import MCPResponse


class TestCalculatorServer(unittest.TestCase):

    def test_add(self):
        result = add(a=1, b=2)
        self.assertEqual(result, MCPResponse.success(result=3).to_dict())

    def test_subtract(self):
        result = subtract(a=5, b=2)
        self.assertEqual(result, MCPResponse.success(result=3).to_dict())

    def test_multiply(self):
        result = multiply(a=3, b=4)
        self.assertEqual(result, MCPResponse.success(result=12).to_dict())

    def test_divide(self):
        result = divide(a=8, b=4)
        self.assertEqual(result, MCPResponse.success(result=2.0).to_dict())

    def test_divide_by_zero(self):
        result = divide(a=8, b=0)
        self.assertEqual(result, MCPResponse.error("Cannot divide by zero").to_dict())


if __name__ == "__main__":
    unittest.main()


class TestAdvancedCalculatorFunctions(unittest.TestCase):

    def test_power(self):
        self.assertEqual(
            power(base=2, exponent=3), MCPResponse.success(result=8).to_dict()
        )

    def test_sqrt(self):
        self.assertEqual(sqrt(number=9), MCPResponse.success(result=3.0).to_dict())

    def test_sqrt_negative(self):
        self.assertEqual(
            sqrt(number=-1),
            MCPResponse.error(
                "Cannot calculate the square root of a negative number"
            ).to_dict(),
        )

    def test_log(self):
        self.assertAlmostEqual(log(number=1)["result"], 0.0)

    def test_log_non_positive(self):
        self.assertEqual(
            log(number=0),
            MCPResponse.error(
                "Cannot calculate the logarithm of a non-positive number"
            ).to_dict(),
        )

    def test_log2(self):
        self.assertAlmostEqual(log2(number=8)["result"], 3.0)

    def test_log10(self):
        self.assertAlmostEqual(log10(number=100)["result"], 2.0)

    def test_sin(self):
        self.assertAlmostEqual(sin(number=0)["result"], 0.0)

    def test_cos(self):
        self.assertAlmostEqual(cos(number=0)["result"], 1.0)

    def test_tan(self):
        self.assertAlmostEqual(tan(number=0)["result"], 0.0)

    def test_sinh(self):
        self.assertAlmostEqual(sinh(number=0)["result"], 0.0)

    def test_cosh(self):
        self.assertAlmostEqual(cosh(number=0)["result"], 1.0)

    def test_tanh(self):
        self.assertAlmostEqual(tanh(number=0)["result"], 0.0)

    def test_asin(self):
        self.assertAlmostEqual(asin(number=0)["result"], 0.0)

    def test_asin_out_of_range(self):
        self.assertEqual(
            asin(number=2),
            MCPResponse.error("Input must be between -1 and 1 for asin").to_dict(),
        )

    def test_acos(self):
        self.assertAlmostEqual(acos(number=1)["result"], 0.0)

    def test_acos_out_of_range(self):
        self.assertEqual(
            acos(number=2),
            MCPResponse.error("Input must be between -1 and 1 for acos").to_dict(),
        )

    def test_atan(self):
        self.assertAlmostEqual(atan(number=0)["result"], 0.0)

    def test_abs(self):
        self.assertEqual(abs(number=-5), MCPResponse.success(result=5.0).to_dict())

    def test_ceil(self):
        self.assertEqual(ceil(number=4.2), MCPResponse.success(result=5).to_dict())

    def test_floor(self):
        self.assertEqual(floor(number=4.8), MCPResponse.success(result=4).to_dict())

    def test_factorial(self):
        self.assertEqual(factorial(number=5), MCPResponse.success(result=120).to_dict())

    def test_factorial_negative(self):
        self.assertEqual(
            factorial(number=-1),
            MCPResponse.error(
                "Cannot calculate the factorial of a negative number"
            ).to_dict(),
        )
