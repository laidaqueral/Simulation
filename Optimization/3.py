import pulp


class DistributionNetwork:
    def __init__(self):
        self.facilities = list()
        self.service_areas = list()
        self.capacity = dict()
        self.opening_costs = dict()
        self.demand = dict()
        self.unit_selling_price = dict()
        self.unit_shipping_cost = dict()
        self.budget = int()

        self.carriers = list()
        self.max_volume = dict()
        self.carrier_multiplier = dict()

    def load(self, facility_file, service_area_file, budget_file, carrier_file):
        # Loads the facilities, service areas, budget and carriers from the four given files.
        # Each file is read by its own helper function below.
        self._load_facilities(facility_file)
        self._load_service_areas(service_area_file)
        self._load_budget(budget_file)
        self._load_carriers(carrier_file)

    def _load_facilities(self, facility_file):
        # Reads lines like: F1;800;450;{'S1': 4, 'S2': 3, ...}
        # Pattern: "Reading and storing data", Reading and writing files slide 14
        # (open the file, skip the header with f.readline(), loop over the lines,
        # split each line into cells and convert/clean every cell), and f.close() as on slide 10.
        f = open(facility_file)
        f.readline()
        for line in f:
            line = line.strip()
            if line == "":
                continue
            cells = line.split(";")
            facility = cells[0].strip()
            # Store the properties in dictionaries keyed by the facility.
            # Pattern: Dictionaries slide 4 (adding a key: my_truck["location"] = "base").
            self.facilities.append(facility)
            self.capacity[facility] = int(cells[1].strip())
            self.opening_costs[facility] = int(cells[2].strip())
            self.unit_shipping_cost[facility] = self._parse_shipping_costs(cells[3])
        f.close()

    def _parse_shipping_costs(self, text):
        # Turns the text "{'S1': 4, 'S2': 3}" into the dictionary {"S1": 4, "S2": 3}.
        # Pattern: Strings slide 8 (replace) and slide 9 (strip) to clean the text,
        # Reading and writing files slide 13/14 (split a line into cells), and
        # Dictionaries slide 4 (adding key/value pairs to a dictionary).
        costs = dict()
        text = text.strip().replace("{", "").replace("}", "")
        for pair in text.split(","):
            parts = pair.split(":")
            service_area = parts[0].strip().replace("'", "").replace('"', "")
            costs[service_area] = int(parts[1].strip())
        return costs

    def _load_service_areas(self, service_area_file):
        # Reads lines like: S1;250;15
        # Pattern: Reading and writing files slide 14 (skip header, split, convert cells),
        # f.close() as on slide 10, and Dictionaries slide 4 (adding key/value pairs).
        f = open(service_area_file)
        f.readline()
        for line in f:
            line = line.strip()
            if line == "":
                continue
            cells = line.split(";")
            service_area = cells[0].strip()
            self.service_areas.append(service_area)
            self.demand[service_area] = int(cells[1].strip())
            self.unit_selling_price[service_area] = int(cells[2].strip())
        f.close()

    def _load_budget(self, budget_file):
        # The budget is the single value on the line below the header.
        # Pattern: Reading and writing files slide 14 (f.readline() to skip the header,
        # then read the next line and convert it with int(...strip())), f.close() as on slide 10.
        f = open(budget_file)
        f.readline()
        self.budget = int(f.readline().strip())
        f.close()


    def _load_carriers(self, carrier_file):
        # Reads lines like: C1;500;[('S1', 0.9), ('S2', 1.1)]
        # Pattern: Reading and writing files slide 14 (skip header, split, convert cells),
        # f.close() as on slide 10, and Dictionaries slide 4 (adding key/value pairs).
        f = open(carrier_file)
        f.readline()
        for line in f:
            line = line.strip()
            if line == "":
                continue
            cells = line.split(";")
            carrier = cells[0].strip()
            self.carriers.append(carrier)
            self.max_volume[carrier] = int(cells[1].strip())
            # Stored like unit_shipping_cost: carrier_multiplier[carrier][service_area] = multiplier
            self.carrier_multiplier[carrier] = self._parse_multipliers(cells[2])
        f.close()

    def _parse_multipliers(self, text):
        # Turns the text "[('S1', 0.9), ('S2', 1.1)]" into the dictionary {"S1": 0.9, "S2": 1.1}.
        # Pattern: Strings slide 8 (replace) and slide 9 (strip) to clean the text,
        # Reading and writing files slide 13/14 (split into cells), and
        # Dictionaries slide 4 (adding key/value pairs to a dictionary).
        multipliers = dict()
        text = text.strip().replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        for pair in text.split("),"):
            pair = pair.strip().replace("(", "").replace(")", "")
            if pair == "":
                continue
            parts = pair.split(",")
            multipliers[parts[0].strip()] = float(parts[1].strip())
        return multipliers

    def solve(self):
        # All slide references below are to the Module 7 lecture
        # "Business Process Optimization" (slide numbers as printed on the slides).
        F = self.facilities
        S = self.service_areas
        C = self.carriers

        # All (facility, service area, carrier) combinations that are possible:
        # a carrier can only ship to the service areas it serves.
        routes = [(f, s, c) for f in F for s in S for c in C if s in self.carrier_multiplier[c]]

        # Actual unit shipping cost of a route = carrier multiplier * original unit shipping cost.
        cost = {(f, s, c): self.carrier_multiplier[c][s] * self.unit_shipping_cost[f][s]
                for (f, s, c) in routes}

        # Problem definition with a maximization objective
        # Pattern: slide 16 (pulp.LpProblem(..., pulp.LpMaximize))
        self._problem = pulp.LpProblem("CFLP_carriers", pulp.LpMaximize)

        # DECISION VARIABLE X[(f,s,c)] >= 0: number of units shipped from facility f to
        # service area s by carrier c (only for carriers that serve s).
        # Pattern: slide 16 (pulp.LpVariable(name, 0)) written compactly with
        # pulp.LpVariable.dicts over all (f,s,c) combinations as on slide 20.
        X = pulp.LpVariable.dicts("X", routes, 0)

        # DECISION VARIABLE Y[f] in {0,1}: 1 if facility f is opened, 0 otherwise.
        # Pattern: slide 20 (pulp.LpVariable.dicts(..., 0, 1, cat=pulp.LpInteger)).
        Y = pulp.LpVariable.dicts("Y", (f for f in F), 0, 1, cat=pulp.LpInteger)

        # OBJECTIVE: maximize profit =
        #   sum over (f,s,c) of (price_s - multiplier_c,s * shipping_cost_f,s) * X_f,s,c
        #   - sum over f of opening_cost_f * Y_f
        # Pattern: slide 21 (problem += pulp.lpSum([P[(r,a)] * X[(r,a)] for r in R for a in A])),
        # with Maximize as on slide 16; product of two parameters times X as on slide 27 (C_r * P_r,a * X_r,a).
        self._problem += (
            pulp.lpSum([(self.unit_selling_price[s] - cost[(f, s, c)]) * X[(f, s, c)]
                        for (f, s, c) in routes])
            - pulp.lpSum([self.opening_costs[f] * Y[f] for f in F])
        )

        # CONSTRAINT 1 (demand): a service area cannot receive more than its demand.
        #   sum over f,c of X_f,s,c <= demand_s, for all s in S
        # Pattern: slide 22 (for a in A: problem += pulp.lpSum([X[(r,a)] for r in R]) == 1),
        # with "<= upper bound" instead of "== 1" as on slide 30.
        for s in S:
            self._problem += pulp.lpSum([X[(f, s2, c)] for (f, s2, c) in routes if s2 == s]) <= self.demand[s]

        # CONSTRAINT 2 (capacity): a facility can ship at most its capacity, and only if it is opened.
        #   sum over s,c of X_f,s,c <= capacity_f * Y_f, for all f in F
        # Pattern: slide 30 (sum over a in A of P_r,a * X_r,a <= 15, for all r in R:
        # a resource can be used up to its maximum availability).
        for f in F:
            self._problem += pulp.lpSum([X[(f2, s, c)] for (f2, s, c) in routes if f2 == f]) <= self.capacity[f] * Y[f]

        # CONSTRAINT 3 (carrier volume): a carrier can ship at most its maximum volume.
        #   sum over f,s of X_f,s,c <= max_volume_c, for all c in C
        # Pattern: slide 30 (sum over a in A of P_r,a * X_r,a <= 15, for all r in R:
        # a resource can be used up to its maximum availability).
        for c in C:
            self._problem += pulp.lpSum([X[(f, s, c2)] for (f, s, c2) in routes if c2 == c]) <= self.max_volume[c]

        # CONSTRAINT 4 (budget): opening costs plus shipping costs may not exceed the budget.
        #   sum over f of opening_cost_f * Y_f + sum over (f,s,c) of multiplier_c,s * shipping_cost_f,s * X_f,s,c <= budget
        # Pattern: slide 13/16 (linear constraint a1*X1 + ... + an*Xn <= b, e.g. 2*X1 + 3*X2 <= 15),
        # written compactly with pulp.lpSum as on slide 21.
        self._problem += (
            pulp.lpSum([self.opening_costs[f] * Y[f] for f in F])
            + pulp.lpSum([cost[(f, s, c)] * X[(f, s, c)] for (f, s, c) in routes])
            <= self.budget
        )

        # Solve and read the status. Pattern: slide 16 (problem.solve(), pulp.LpStatus[problem.status]).
        self._problem.solve(pulp.PULP_CBC_CMD(msg=False))
        self.status = pulp.LpStatus[self._problem.status]

        # Build the result: (facility, service area, carrier, amount) for every non-zero allocation.
        # Pattern: slide 16 (reading v.varValue after solving).
        solution = []
        for (f, s, c) in routes:
            amount = X[(f, s, c)].varValue
            if amount is not None and amount > 1e-6:
                solution.append((f, s, c, float(amount)))

        self._compute_statistics(solution, Y)
        return solution

    def _compute_statistics(self, solution, Y):
        # Helper that fills in the attributes printed by the solution check.
        self.facilities_opened = [f for f in self.facilities
                                  if Y[f].varValue is not None and Y[f].varValue > 0.5]
        self.demand_met = {s: 0.0 for s in self.service_areas}
        self.volume_used = {c: 0.0 for c in self.carriers}
        for f, s, c, amount in solution:
            self.demand_met[s] += amount
            self.volume_used[c] += amount
        self.demand_unmet = {s: self.demand[s] - self.demand_met[s] for s in self.service_areas}

        self.total_revenue = sum(self.unit_selling_price[s] * amount for f, s, c, amount in solution)
        self.total_opening_cost = sum(self.opening_costs[f] for f in self.facilities_opened)
        self.total_shipping_cost = sum(self.carrier_multiplier[c][s] * self.unit_shipping_cost[f][s] * amount
                                       for f, s, c, amount in solution)
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
problem.load(
    "3_1_facilities.txt", "3_1_service_areas.txt", "3_1_budget.txt", "3_1_carriers.txt"
)
# problem.load(
#     "3_2_facilities.txt", "3_2_service_areas.txt", "3_2_budget.txt", "3_2_carriers.txt"
# )  # You can uncomment this line to evaluate another problem instance

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
    "- The solution is a list of 4-tuples:",
    (
        type(solution) == list
        and all([type(sol) == tuple and len(sol) == 4 for sol in solution])
        if len(solution) > 0
        else False
    ),
)
print(
    "- All variables are loaded:",
    (
        len(problem.facilities) > 0
        and len(problem.service_areas) > 0
        and len(problem.capacity) > 0
        and len(problem.opening_costs) > 0
        and len(problem.demand) > 0
        and len(problem.unit_selling_price) > 0
        and len(problem.unit_shipping_cost) > 0
        and problem.budget > 0
        and len(problem.carriers) > 0
        and len(problem.max_volume) > 0
        and len(problem.carrier_multiplier) > 0
    ),
)
print("- Allocation plan:")
print(solution)

print("- Facilities opened:", problem.facilities_opened)

print("- Carrier volume:")
for c in problem.carriers:
    used = problem.volume_used[c]
    available = problem.max_volume[c]
    print(f"*  {c}: used {used} of {available} (remaining {available - used})")

print(f"- Total demand met: {sum(problem.demand_met.values())} / {sum(problem.demand.values())}")

print("- Demand fulfillment:")
for s in problem.service_areas:
    met = problem.demand_met[s]
    total = problem.demand[s]
    unmet = problem.demand_unmet[s]
    print(f"*  {s}: met {met} of {total} (unmet {unmet})")

print("DONE\n")