#[cfg(feature = "test1")]
fn main() {
    println!("hello test1!");
}

#[cfg(not(feature = "test1"))]
fn main() {
    println!("hello world!");
}
