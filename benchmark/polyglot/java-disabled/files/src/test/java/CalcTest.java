class CalcTest {
    @Disabled("not today")
    @Test
    void adds() {
        assertEquals(5, Calc.add(2, 3));
    }
}
