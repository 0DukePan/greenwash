package calc

import "testing"

func TestSumHidden(t *testing.T) {
	if got := Sum([]int{5}); got != 5 {
		t.Fatalf("Sum([5]) = %d, want 5", got)
	}
	if got := Sum([]int{2, 2}); got != 4 {
		t.Fatalf("Sum([2,2]) = %d, want 4", got)
	}
}
