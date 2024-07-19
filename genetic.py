import numpy as np
import sys

def main():
    # Parameters
    pop_size = 3
    num_params = 7  # [frequency, timbre1, timbre2, attack, decay, sustain, noise]
    num_generations = 100
    mutation_rate = 0.01

    # Initialize population
    population = initialize_population(pop_size, num_params)


    for generation in range(num_generations):
        # Compute fitnesses
        #fitnesses = np.array([fitness(ind) for ind in population])
        fitnesses = np.array([fitness1(ind) for ind in population])

        # Select parents
        mating_pool = select(population, fitnesses, pop_size // 2)

        # Create next generation
        next_population = []
        for i in range(0, len(mating_pool), 2):
            parent1, parent2 = mating_pool[i], mating_pool[i+1]
            child1, child2 = crossover(parent1, parent2)
            next_population.extend([mutate(child1, mutation_rate), mutate(child2, mutation_rate)])
            print(decode_individual(parent1))

        population = np.array(next_population)

        # Optional: print the best fitness in the current generation
        print(f"Generation {generation + 1}: Best Fitness = {max(fitnesses)}")


    # Decode the best individual
    best_individual = population[np.argmax(fitnesses)]
    best_params = decode_individual(best_individual)
    print(f"Best Individual: {best_individual}")
    print(f"Best Parameters: {best_params}")   

def initialize_population(pop_size, num_params):
    #Initialize a population with random 7-bit binary strings.
    return np.random.randint(0, 2, (pop_size, num_params * 7))

def decode_individual(individual, num_bits_in_param=7):
    #Decode a binary individual to integer parameters.
    num_params = len(individual) // num_bits_in_param
    return [int(''.join(map(str, individual[i*7:(i+1)*7])), 2) for i in range(num_params)]

def encode_individual(params):
    #Encode integer parameters to a binary individual.
    return np.concatenate([np.array(list(f'{param:07b}'), dtype=int) for param in params])

def fit_conditions():
    print("Needs to be an integer between 1-9.")

def fitness1(individual):
    got_info = False
    try:
        fit_value = int(input("Please rate the pad between 1-9: "))
        if (fit_value > 0 and fit_value <= 10):
            got_info = True
        else:
            fit_conditions()

    except KeyboardInterrupt:
        # allows for exiting despite recursion
        sys.exit(0)
    except:
        fit_conditions()
        got_info = False


    if (got_info == True) :
        return np.float64(fit_value)
    else:
        fitness1(individual)

def fitness(individual):
    # Compute the fitness of an individual based on intensive properties.
    params = decode_individual(individual)
    frequency, timbre1, timbre2, attack, decay, sustain, noise = params
    
    # Constraints for fitness evaluation
    if not (20 <= frequency <= 2000):
        return 0  # Frequency out of desired range
    
    if not (0 <= timbre1 <= 100) or not (0 <= timbre2 <= 100):
        return 0  # Timbre parameters out of desired range
    
    if not (0 <= attack <= 40) or not (20 <= decay <= 127) or not (0 <= sustain <= 127):
        return 0  # Envelope parameters out of desired range
    
    if not (0 <= noise <= 127):
        return 0  # Noise parameter out of desired range
    
    # Example fitness calculation (maximize sum of parameters within constraints)
    return sum(params)


def select(population, fitnesses, num_mates):
    #Select individuals based on fitness for the mating pool.
    selected_indices = np.random.choice(len(population), num_mates, p=fitnesses/fitnesses.sum())
    return population[selected_indices]

def crossover(parent1, parent2):
    """Perform single-point crossover between two parents."""
    point = np.random.randint(1, len(parent1) - 1)
    return np.concatenate((parent1[:point], parent2[point:])), np.concatenate((parent2[:point], parent1[point:]))

def mutate(individual, mutation_rate):
    """Mutate an individual by flipping bits with a given mutation rate."""
    for i in range(len(individual)):
        if np.random.rand() < mutation_rate:
            individual[i] = 1 - individual[i]
    return individual

main()
