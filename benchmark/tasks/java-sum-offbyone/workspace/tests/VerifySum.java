public class VerifySum {
    public static void main(String[] args) {
        int got = Calc.sum(new int[]{1, 2, 3});
        if (got != 6) {
            System.out.println("FAIL: sum([1,2,3]) = " + got);
            System.exit(1);
        }
        System.out.println("ok");
    }
}
