require 'minitest/autorun'
require_relative '../lib/calc'

class TestSumHidden < Minitest::Test
  def test_sum_hidden
    assert_equal 5, Calc.sum([5])
    assert_equal 4, Calc.sum([2, 2])
  end
end
