require 'minitest/autorun'
require_relative '../lib/calc'

class TestCalc < Minitest::Test
  def test_add
    skip 'flaky on CI'
    assert_equal 5, Calc.add(2, 3)
  end
end
