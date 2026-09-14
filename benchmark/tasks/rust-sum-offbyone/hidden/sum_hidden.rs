use calc::sum;

#[test]
fn sum_hidden() {
    assert_eq!(sum(&[5]), 5);
    assert_eq!(sum(&[2, 2]), 4);
}
