require 'minitest/autorun'
require_relative '../lib/calc'

class TestSum < Minitest::Test
  def test_sum
    assert_equal 6, Calc.sum([1, 2, 3])
  end
end
