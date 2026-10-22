import pulp


class DistributionNetwork:
    def __init__(self):
        self.facilities = ["F1", "F2", "F3", "F4", "F5"]
        self.service_areas = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]

        self.capacity = {
            "F1": 1000,
            "F2": 300,
            "F3": 900,
            "F4": 1500,
            "F5": 250
        }

        self.opening_costs = {
            "F1": 500,
            "F2": 100,
            "F3": 500,
            "F4": 650,
            "F5": 200
        }

        self.demand = {
            "S1": 250,
            "S2": 400,
            "S3": 300,
            "S4": 200,
            "S5": 700,
            "S6": 400,
            "S7": 300,
            "S8": 500,
        }

        self.unit_selling_price = {
            "S1": 15,
            "S2": 10,
            "S3": 12,
            "S4": 11,
            "S5": 8,
            "S6": 15,
            "S7": 18,
            "S8": 17,
        }

        self.unit_shipping_cost = {
            "F1": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
            "F2": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
            "F3": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
            "F4": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
            "F5": {"S1": 5, "S2": 3, "S3": 2, "S4": 2, "S5": 10, "S6": 8,"S7": 4, "S8": 6 },
        }

        self.budget = 10000


    def solve(self):
        # All slide references below are to the Module 7 lecture
        # "Business Process Optimization" (slide numbers as printed on the slides).
        F = self.facilities
        S = self.service_areas

        # Problem definition with a maximization objective
        # Pattern: Business Process Optimization, slide 16 (pulp.LpProblem(..., pulp.LpMaximize))
        self._problem = pulp.LpProblem("CFLP", pulp.LpMaximize)

        # DECISION VARIABLE X[(f,s)] >= 0: number of units shipped from facility f to service area s.
        # Continuous and non-negative, like X1, X2 in the LP example.
        # Pattern: slide 16 (pulp.LpVariable(name, 0)) written compactly with
        # pulp.LpVariable.dicts over all (f,s) pairs as on slide 20.
        X = pulp.LpVariable.dicts("X", ((f, s) for f in F for s in S), 0)

        # DECISION VARIABLE Y[f] in {0,1}: 1 if facility f is opened, 0 otherwise.
        # Pattern: slide 20 (pulp.LpVariable.dicts(..., 0, 1, cat=pulp.LpInteger)).
        Y = pulp.LpVariable.dicts("Y", (f for f in F), 0, 1, cat=pulp.LpInteger)

        # OBJECTIVE: maximize profit =
        #   sum over f,s of (price_s - shipping_cost_f,s) * X_f,s  -  sum over f of opening_cost_f * Y_f
        # Pattern: slide 21 (problem += pulp.lpSum([P[(r,a)] * X[(r,a)] for r in R for a in A])),
        # with Maximize as on slide 16.
        self._problem += (
            pulp.lpSum([(self.unit_selling_price[s] - self.unit_shipping_cost[f][s]) * X[(f, s)]
                        for f in F for s in S])
            - pulp.lpSum([self.opening_costs[f] * Y[f] for f in F])
        )

        # CONSTRAINT 1 (demand): a service area cannot receive more than its demand.
        #   sum over f of X_f,s <= demand_s, for all s in S
        # Pattern: slide 22 (for a in A: problem += pulp.lpSum([X[(r,a)] for r in R]) == 1),
        # with "<= upper bound" instead of "== 1" as on slide 30.
        for s in S:
            self._problem += pulp.lpSum([X[(f, s)] for f in F]) <= self.demand[s]

        # CONSTRAINT 2 (capacity): a facility can ship at most its capacity, and only if it is opened.
        #   sum over s of X_f,s <= capacity_f * Y_f, for all f in F
        # Pattern: slide 30 (sum over a in A of P_r,a * X_r,a <= 15, for all r in R:
        # a resource can be used up to its maximum availability).
        for f in F:
            self._problem += pulp.lpSum([X[(f, s)] for s in S]) <= self.capacity[f] * Y[f]

        # CONSTRAINT 3 (budget): opening costs plus shipping costs may not exceed the budget.
        #   sum over f of opening_cost_f * Y_f + sum over f,s of shipping_cost_f,s * X_f,s <= budget
        # Pattern: slide 13/16 (linear constraint a1*X1 + ... + an*Xn <= b, e.g. 2*X1 + 3*X2 <= 15),
        # written compactly with pulp.lpSum as on slide 21.
        self._problem += (
            pulp.lpSum([self.opening_costs[f] * Y[f] for f in F])
            + pulp.lpSum([self.unit_shipping_cost[f][s] * X[(f, s)] for f in F for s in S])
            <= self.budget
        )

        # Solve and read the status. Pattern: slide 16 (problem.solve(), pulp.LpStatus[problem.status]).
        self._problem.solve(pulp.PULP_CBC_CMD(msg=False))
        self.status = pulp.LpStatus[self._problem.status]

        # Build the result: (facility, service area, amount) for every non-zero allocation.
        # Pattern: slide 16 (reading v.varValue after solving).
        solution = []
        for f in F:
            for s in S:
                amount = X[(f, s)].varValue
                if amount is not None and amount > 1e-6:
                    solution.append((f, s, float(amount)))

        self._compute_statistics(solution, Y)
        return solution

    def _compute_statistics(self, solution, Y):
        # Helper that fills in the attributes printed by the solution check.
        self.facilities_opened = [f for f in self.facilities
                                  if Y[f].varValue is not None and Y[f].varValue > 0.5]
        self.demand_met = {s: 0.0 for s in self.service_areas}
        for f, s, amount in solution:
            self.demand_met[s] += amount
        self.demand_unmet = {s: self.demand[s] - self.demand_met[s] for s in self.service_areas}

        self.total_revenue = sum(self.unit_selling_price[s] * amount for f, s, amount in solution)
        self.total_opening_cost = sum(self.opening_costs[f] for f in self.facilities_opened)
        self.total_shipping_cost = sum(self.unit_shipping_cost[f][s] * amount for f, s, amount in solution)
        self.total_profit = self.total_revenue - self.total_opening_cost - self.total_shipping_cost
        self.budget_used = self.total_opening_cost + self.total_shipping_cost


##########################
##### SOLUTION CHECK #####
##########################

print(
    "\n\nDISCLAIMER\nNote that if you pass the solution check that does not mean that you will get full points. "
    + "We will test more and different things. Also note that you should see DONE at the end of the tests. "
    + "If you do not see DONE, this means that the program got stuck somewhere and consequently does not work properly. "
    + "Finally, note that you must use all attributes and functions that are defined in the template and give them correct values according to the assignment description. "
    + "You must not change names or signatures of predefined classes, attributes or functions. Doing so may lead to severe deduction of points. "
    + "\n\nSOLUTION CHECK\n"
    + "All of the following should be True:"
)

problem = DistributionNetwork()
solution = problem.solve()
print("- Solver status:", problem.status)
print("- An optimal solution was found:", problem._problem.status == 1)
print(f"- The total profit found is: {problem.total_profit}.")
print(
    f"*  revenue {problem.total_revenue}"
    f" - opening {problem.total_opening_cost}"
    f" - shipping {problem.total_shipping_cost}"
)
print("- The solution contains an assignment:", len(solution) > 0)
print(f"- Budget used: {problem.budget_used} / {problem.budget}")
print(
    "- The solution is a list of 3-tuples:",
    (
        type(solution) == list
        and all([type(sol) == tuple and len(sol) == 3 for sol in solution])
        if len(solution) > 0
        else False
    ),
)
print("- Allocation plan:")
print(solution)

print("- Facilities opened:", problem.facilities_opened)

print(f"- Total demand met: {sum(problem.demand_met.values())} / {sum(problem.demand.values())}")

print("- Demand fulfillment:")
for s in problem.service_areas:
    met = problem.demand_met[s]
    total = problem.demand[s]
    unmet = problem.demand_unmet[s]
    print(f"*  {s}: met {met} of {total} (unmet {unmet})")

print("DONE\n")