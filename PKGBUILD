# Maintainer: storchdev
pkgname=calslop
pkgver=r103.39a5e16
pkgrel=1
pkgdesc="Personal calendar and todo app"
arch=('any')
url="https://github.com/storchdev/calslop"
license=('MIT')
depends=('python' 'nodejs' 'npm')
makedepends=('git' 'uv')
options=('!debug' '!strip')
install=calslop.install
source=("${pkgname}::git+https://github.com/storchdev/calslop.git")
sha256sums=('SKIP')

_port=8765

pkgver() {
    cd "$srcdir/$pkgname"
    printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

build() {
    cd "$srcdir/$pkgname"

    echo "Building backend..."
    cd backend
    uv sync --no-dev
    cd ..

    echo "Building frontend..."
    cd frontend
    npm ci
    npm run build
    cd ..
}

package() {
    cd "$srcdir/$pkgname"

    # Install app files
    install -dm755 "$pkgdir/opt/$pkgname"
    cp -a backend frontend bin "$pkgdir/opt/$pkgname/"

    # Remove frontend node_modules and source to keep only the build output
    rm -rf "$pkgdir/opt/$pkgname/frontend/node_modules"
    rm -rf "$pkgdir/opt/$pkgname/frontend/src"

    # Install the management script
    install -Dm755 bin/calslop "$pkgdir/usr/bin/calslop"

    # Install the systemd user unit
    install -Dm644 /dev/stdin "$pkgdir/usr/lib/systemd/user/calslop.service" <<EOF
[Unit]
Description=Calslop calendar and todo app
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/calslop/backend
Environment="PYTHONPATH=/opt/calslop/backend"
Environment="CALSLOP_STATIC_DIR=/opt/calslop/frontend/build"
Environment="PATH=/opt/calslop/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/calslop/backend/.venv/bin/python -m flask --app app.main run --port $_port --host 0.0.0.0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
}
