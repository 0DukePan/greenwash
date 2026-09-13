RSpec.describe Client do
  it 'times out' do
    http = double('http')
    allow(http).to receive(:get).and_return(nil)
    expect(Client.new(http).fetch).to be_nil
  end
end
