from svg.path import parse_path
import numpy as np

path = parse_path('M 100 100 L 300 100 L 100 300')
for x in np.linspace(0,1,21):
    print(path.point(x))

    