public class VerifySumHidden {
    public static void main(String[] args) {
        int got = Calc.sum(new int[]{5});
        if (got != 5) {
            System.out.println("FAIL: sum([5]) = " + got);
            System.exit(1);
        }
        int two = Calc.sum(new int[]{2, 2});
        if (two != 4) {
            System.out.println("FAIL: sum([2,2]) = " + two);
            System.exit(1);
        }
        System.out.println("ok");
    }
}
