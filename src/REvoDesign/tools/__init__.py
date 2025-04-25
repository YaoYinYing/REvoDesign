'''
Tools module used by REvoDesign and its satellite functions.

# TODO

FoldIt-like behavior:
- spikal sphere indicating spatal crashes (CGO)
    Class SpikalSphere(GO):
        scale: float # indicating the crash level
        location: Point # crash coordinates

        color: str= 'red'
        opacity: float = 1

    
- half opaque sphere indicating spatial void (CGO)
    Class VoidSphere(GO):
        scale: float # indicating the void level
        location: Point # void coordinates

        color: str = 'white'
        opacity: float = 0.5
'''